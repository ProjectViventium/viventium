#!/usr/bin/env python3
"""Read one Queen turn's existing timing evidence; never emit prompt or reasoning text."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

UNKNOWN = "UNKNOWN"
ID = re.compile(r"^[A-Za-z0-9._:-]{1,192}$")


def iso(value):
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(value / 1000, dt.timezone.utc).isoformat()
    if not isinstance(value, str):
        return UNKNOWN
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return UNKNOWN


def public_message(payload):
    """Observe nonempty public response-envelope candidates; do not validate admission."""
    if payload.get("type") != "message" or payload.get("role") != "assistant":
        return False
    if payload.get("channel") not in (None, "final", "commentary"):
        return False
    for part in payload.get("content", []):
        if part.get("type") not in ("output_text", "text"):
            continue
        try:
            envelope = json.loads(part.get("text", ""))
        except (ValueError, TypeError):
            continue
        if (isinstance(envelope, dict) and envelope.get("type") == "assistant_response"
                and isinstance(envelope.get("content"), str) and envelope["content"].strip()
                and envelope["content"].strip() != "{NTA}" and envelope.get("tool_name") is None):
            return True
    return False


def native_events(lines, started_at=None, ended_at=None):
    result = {key: UNKNOWN for key in ("task_started", "context_ready", "first_complete_public_answer",
                                      "first_completed_public_commentary", "effective_model", "effective_effort", "first_usage")}
    result["public_tool_calls"] = []
    for line in lines:
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        timestamp = iso(event.get("timestamp"))
        if started_at and (timestamp == UNKNOWN or dt.datetime.fromisoformat(timestamp) < dt.datetime.fromisoformat(iso(started_at))):
            continue
        if ended_at and (timestamp == UNKNOWN or dt.datetime.fromisoformat(timestamp) > dt.datetime.fromisoformat(iso(ended_at))):
            continue
        body = event.get("payload", {})
        if not isinstance(body, dict):
            continue
        kind = event.get("type")
        if kind == "event_msg" and body.get("type") == "item_completed":
            item = body.get("item") or {}
            if (item.get("type") == "AgentMessage" and item.get("phase") == "commentary"
                    and item.get("content") and result["first_completed_public_commentary"] == UNKNOWN):
                result["first_completed_public_commentary"] = timestamp
            if item.get("type") == "McpToolCall":
                duration = item.get("duration") or {}
                secs, nanos = duration.get("secs"), duration.get("nanos")
                elapsed = round(secs * 1000 + nanos / 1000000, 3) if isinstance(secs, (int, float)) and isinstance(nanos, (int, float)) and secs >= 0 and nanos >= 0 else UNKNOWN
                result["public_tool_calls"].append({"completed_at": timestamp, "duration_ms": elapsed,
                    "status": item.get("status") if item.get("status") in ("completed", "failed", "in_progress") else UNKNOWN})
        if kind == "event_msg" and body.get("type") == "task_started":
            result["task_started"] = iso(event.get("timestamp"))
        elif kind == "turn_context":
            result["context_ready"] = iso(event.get("timestamp"))
            result["effective_model"] = body.get("model") or UNKNOWN
            result["effective_effort"] = body.get("effort") or UNKNOWN
        elif kind == "response_item" and public_message(body) and result["first_complete_public_answer"] == UNKNOWN:
            result["first_complete_public_answer"] = iso(event.get("timestamp"))
        elif kind == "event_msg" and body.get("type") == "token_count" and result["first_usage"] == UNKNOWN:
            usage = (body.get("info") or {}).get("last_token_usage")
            if isinstance(usage, dict):
                result["first_usage"] = {k: usage.get(k, UNKNOWN) for k in
                    ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")}
    # Legacy field above observes an assistant_response candidate, not runtime admission.
    result["response_envelope_candidate"] = result["first_complete_public_answer"]
    durations = [row["duration_ms"] for row in result["public_tool_calls"]]
    result["public_tool_duration_sum_ms"] = round(sum(durations), 3) if durations and UNKNOWN not in durations else UNKNOWN
    return result


def native_stdout_metadata(lines):
    result = {}
    for line in lines:
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            result["effective_model"] = event.get("model") or UNKNOWN
        if event.get("type") == "result" and isinstance(event.get("usage"), dict):
            result["total_run_usage"] = {key: event["usage"].get(key, UNKNOWN) for key in
                                       ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    return result


def core_forwarding(lines, message_id, run_id=None, run_windows=()):
    found = {}
    for line in lines:
        if "[NativePreview]" not in line:
            continue
        # Logger truncation may remove the JSON tail. Require complete exact fields.
        identity = re.search(r'"messageId":"([^"\\]+)"', line)
        stage = re.search(r'"stage":"(received|emit_submitted|emit_returned)"', line)
        if identity and identity.group(1) == message_id and stage:
            timestamp = iso(line.split(" ", 1)[0])
            if run_id is not None:
                if timestamp == UNKNOWN:
                    continue
                at = dt.datetime.fromisoformat(timestamp)
                matches = []
                for window in run_windows:
                    start, end = iso(window.get("started_at")), iso(window.get("ended_at"))
                    # No guessed grace period or open-ended match for incomplete evidence.
                    if start == UNKNOWN or end == UNKNOWN:
                        matches.append(UNKNOWN)
                        continue
                    if dt.datetime.fromisoformat(start) <= at <= dt.datetime.fromisoformat(end):
                        matches.append(window["run_id"])
                if matches != [run_id]:
                    continue
            found.setdefault(stage.group(1), timestamp)
    return {k: found.get(k, UNKNOWN) for k in ("received", "emit_submitted", "emit_returned")}


MONGO_READ = r'''
const {createRequire}=require('node:module');
const requireLC=createRequire(process.argv[1]+'/api/server/index.js');
const {MongoClient}=requireLC('mongodb');
(async()=>{const client=await MongoClient.connect(process.env[process.argv[3]],{serverSelectionTimeoutMS:5000});
try {const db=client.db();const id=process.argv[2];
const projection={messageId:1,parentMessageId:1,createdAt:1,isCreatedByUser:1,'nativeResponse.source.messageId':1,'nativeResponse.streamId':1,'nativeResponse.logicalTurnId':1,'nativeResponse.revision':1,'nativeResponse.admittedAt':1,'nativeResponse.deliveryDispositionRequired':1};
let row=await db.collection('messages').findOne({messageId:id},{projection});
const source=row?.isCreatedByUser?row:null;
if(source)row=await db.collection('messages').findOne({'nativeResponse.source.messageId':id},{projection,sort:{createdAt:-1}});
const input=source||await db.collection('messages').findOne({messageId:row?.nativeResponse?.source?.messageId||row?.parentMessageId},{projection});
let channelAck=null;
if(process.argv[4]&&process.env[process.argv[4]]&&row?.nativeResponse?.streamId){
 const Redis=requireLC('ioredis');const redis=new Redis(process.env[process.argv[4]],{lazyConnect:true,connectTimeout:3000,maxRetriesPerRequest:0,retryStrategy:()=>null});
 try{await redis.connect();const job=await redis.hgetall((process.argv[5]||'')+'stream:{'+row.nativeResponse.streamId+'}:job');const native=JSON.parse(job.nativeResponse||'null');const ack=JSON.parse(job.deliveryAcknowledgement||'null');
 if(native?.responseMessageId===row.messageId&&native.logicalTurnId===row.nativeResponse.logicalTurnId&&native.revision===row.nativeResponse.revision&&ack?.logical_turn_id===native.logicalTurnId&&ack.revision===native.revision)channelAck={state:ack.state,at:ack.presentation_committed_at||null};
 }catch{}finally{redis.disconnect()}
}
console.log(JSON.stringify({channelAck,responseMessageId:row?.messageId||null,userMessageId:input?.messageId||null,acceptedAt:input?.createdAt||null,nativeAdmittedAt:row?.nativeResponse?.admittedAt||null,deliveryDispositionRequired:row?.nativeResponse?.deliveryDispositionRequired??null}));
}finally{await client.close()}})().catch(()=>{console.log(JSON.stringify({error:'mongo_evidence_unavailable'}));process.exitCode=1});
'''


def mongo_read(root, message_id, env_name, redis_env="", redis_prefix=""):
    if not os.environ.get(env_name):
        return {"error": "mongo_uri_environment_missing"}
    try:
        result = subprocess.run(["node", "-e", MONGO_READ, str(root), message_id, env_name, redis_env, redis_prefix],
                                capture_output=True, text=True, timeout=10, check=False)
        return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"error": "mongo_evidence_unavailable"}


def diagnose(args):
    db = sqlite3.connect(args.glasshive_db.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    mongo = {}
    message_id = args.message_id
    if message_id:
        mongo = mongo_read(args.librechat_root, message_id, args.mongo_uri_env, args.redis_url_env, args.redis_job_key_prefix)
        message_id = mongo.get("responseMessageId") or message_id
    where, value = ("pr.run_id", args.run_id) if args.run_id else ("pr.message_id", message_id)
    rows = db.execute(f"""SELECT pr.request_id,pr.run_id,pr.message_id,pr.created_at,
        pr.replay_decision_json,pr.fallback_state,pr.fallback_from_run_id,
        ps.worker_id,ps.agent_id,ps.actor_kind,ps.origin,r.started_at,r.ended_at,r.native_session_id,
        r.provider_route_model,r.provider_route_decision,r.provider_route_failure_class
        FROM provider_requests pr JOIN provider_sessions ps ON ps.session_id=pr.session_id
        JOIN runs r ON r.run_id=pr.run_id WHERE {where}=? ORDER BY pr.created_at""", (value,)).fetchall()
    if not rows:
        return {"status": "not_found", "mongo": mongo}
    reports = []
    for raw in rows:
        row = dict(raw)
        if not mongo:
            mongo = mongo_read(args.librechat_root, row["message_id"], args.mongo_uri_env, args.redis_url_env, args.redis_job_key_prefix)
        replay = json.loads(row.pop("replay_decision_json") or "{}")
        result = {"identity": {k: row[k] for k in ("request_id", "run_id", "message_id", "agent_id", "actor_kind", "origin")},
                  "accepted_at": iso(mongo.get("acceptedAt")), "provider_admission": iso(row["created_at"]),
                  "native_start": iso(row["started_at"]), "native_end": iso(row["ended_at"]),
                  "requested_model": (replay.get("completion_contract_v1") or {}).get("model", UNKNOWN),
                  "requested_effort": (replay.get("completion_contract_v1") or {}).get("reasoning_effort", UNKNOWN),
                  "route_model": row["provider_route_model"] or UNKNOWN,
                  "fallback_state": row["fallback_state"] or UNKNOWN,
                  "fallback_from_run_id": row["fallback_from_run_id"],
                  "route_decision": row["provider_route_decision"] or UNKNOWN,
                  "route_failure_class": row["provider_route_failure_class"] or None,
                  "replay_mode": replay.get("mode", UNKNOWN)}
        runtime_root = args.glasshive_db.parent
        homes = list(runtime_root.glob(f"*_runtime/workers/{row['worker_id']}/home"))
        files = []
        for home in homes:
            if row["native_session_id"]:
                files.extend((home / ".codex/sessions").glob(f"**/*{row['native_session_id']}*.jsonl"))
        # Never choose one of ambiguous session files or an unrelated worker transcript.
        result["native"] = native_events(files[0].read_text().splitlines(), row["started_at"], row["ended_at"]) if len(files) == 1 else native_events([])
        stdout_files = [home / ".glasshive-runs" / row["run_id"] / "stdout.log" for home in homes]
        stdout_files = [path for path in stdout_files if path.is_file()]
        if len(stdout_files) == 1:
            metadata = native_stdout_metadata(stdout_files[0].read_text().splitlines())
            result["native"].update(metadata)
        # Query every exact-anchor peer even when the CLI selected a single run.
        windows = [dict(peer) for peer in db.execute("""SELECT r.run_id,r.started_at,r.ended_at
            FROM provider_requests pr JOIN runs r ON r.run_id=pr.run_id
            WHERE pr.message_id=?""", (row["message_id"],)).fetchall()]
        result["core_forwarding"] = core_forwarding(args.core_log.read_text().splitlines() if args.core_log else [],
                                                   row["message_id"], row["run_id"], windows)
        result["channel_acknowledgment"] = {"state": mongo["channelAck"].get("state", UNKNOWN), "at": iso(mongo["channelAck"].get("at"))} if mongo.get("channelAck") else UNKNOWN
        result["client_visible_render"] = UNKNOWN
        pairs = {
            "admission_to_native_start": (result["provider_admission"], result["native_start"]),
            "native_start_to_task": (result["native_start"], result["native"]["task_started"]),
            "task_to_context": (result["native"]["task_started"], result["native"]["context_ready"]),
            "context_to_first_completed_public_commentary": (result["native"]["context_ready"], result["native"]["first_completed_public_commentary"]),
            "context_to_first_complete_public_answer": (result["native"]["context_ready"], result["native"]["first_complete_public_answer"]),
            "public_answer_to_core_emit": (result["native"]["first_complete_public_answer"], result["core_forwarding"]["emit_submitted"]),
        }
        result["stage_durations_ms"] = {
            key: round((dt.datetime.fromisoformat(end) - dt.datetime.fromisoformat(start)).total_seconds() * 1000, 3)
            if start != UNKNOWN and end != UNKNOWN else UNKNOWN
            for key, (start, end) in pairs.items()
        }
        result["limits"] = ["first_complete_public_answer and its duration labels are legacy aliases for response_envelope_candidate, not admission or earliest public commentary.",
                            "Candidate shape inspection does not run the owning exact-envelope, graph or voice validator. Admission requires the runtime forwarding receipt; do not infer it from this candidate timestamp.",
                            "Plain public commentary is not an admitted response envelope and is not forwarded by the current delivery contract; it is not hidden reasoning.",
                            "Public tool duration sum is not wall-clock critical path; parallel calls may overlap. Arguments and results are excluded.",
                            "Completed public items only; provider-internal timing split is UNKNOWN.",
                            "Core forwarding requires a unique exact-anchor native run window; missing, overlapping or post-run evidence stays UNKNOWN.",
                            "Agent identity/actor/origin label each request independently; shared anchors do not imply a Main fallback.",
                            "Core emit and channel acknowledgments are not client-visible rendering."]
        if mongo.get("error"):
            result["mongo_evidence"] = mongo["error"]
        reports.append(result)
    return {"status": "observed", "runs": reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--run-id")
    selector.add_argument("--message-id", help="Exact user or assistant message ID")
    parser.add_argument("--glasshive-db", type=Path, required=True)
    parser.add_argument("--librechat-root", type=Path, required=True)
    parser.add_argument("--mongo-uri-env", default="MONGO_URI", help="Environment variable name; never put credentials in arguments")
    parser.add_argument("--core-log", type=Path)
    parser.add_argument("--redis-url-env", default="", help="Optional existing Redis URL environment variable for retained exact-job channel acknowledgment")
    parser.add_argument("--redis-job-key-prefix", default="", help="Exact configured Redis key prefix, if used")
    args = parser.parse_args()
    if not ID.fullmatch(args.run_id or args.message_id):
        parser.error("Invalid exact identity")
    try:
        print(json.dumps(diagnose(args), indent=2))
    except (OSError, sqlite3.Error, ValueError):
        print(json.dumps({"status": "unavailable", "reason": "local_evidence_unavailable"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
