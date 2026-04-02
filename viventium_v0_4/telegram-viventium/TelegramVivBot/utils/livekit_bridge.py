import asyncio
import os
import json
import logging
import time
from typing import Dict, Optional, AsyncIterator, Any, List, Set, Callable, Awaitable
from livekit import api
from livekit import rtc

logger = logging.getLogger(__name__)

# Standard LiveKit Chat Topic - MUST match livekit.agents.types.TOPIC_CHAT
# The agent uses register_text_stream_handler(TOPIC_CHAT) which expects "lk.chat"
LK_CHAT_TOPIC = "lk.chat"

class LiveKitBridge:
    def __init__(self):
        self.url = os.getenv("LIVEKIT_URL")
        self.api_key = os.getenv("LIVEKIT_API_KEY")
        self.api_secret = os.getenv("LIVEKIT_API_SECRET")
        # Agent dispatch name (must match the agent worker's WorkerOptions.agent_name)
        # If the agent is registered with an agent_name, LiveKit requires **explicit dispatch**
        # via AgentDispatchService.CreateDispatch (auto-dispatch will NOT occur).
        self.agent_name = os.getenv("LIVEKIT_AGENT_NAME", "viventium").strip() or "viventium"
        
        if not self.url or not self.api_key or not self.api_secret:
            logger.warning("LiveKit credentials missing! Bridge will not work.")
            
        self.rooms: Dict[int, rtc.Room] = {}
        # Keep the active LiveKit room name per chat_id (helps with re-dispatch retries)
        self.room_names: Dict[int, str] = {}
        self.queues: Dict[int, asyncio.Queue] = {}
        self.tasks: Dict[int, asyncio.Task] = {}
        self.last_activity: Dict[int, float] = {}
        # Track partial/final transcript state per chat to avoid duplicate sends
        self.transcription_state: Dict[int, Dict[str, str]] = {}
        # Track agent connection events per chat (for waiting on agent before sending)
        self.agent_connected_events: Dict[int, asyncio.Event] = {}
        
        # Active chat sessions (chat_id) currently handled by chat_stream
        self.active_chats: Set[int] = set()
        
        # Callback for proactive messages (chat_id, text) -> Awaitable[None]
        self.on_message_callback: Optional[Callable[[int, str], Awaitable[None]]] = None

        # === VIVENTIUM START ===
        # Track room disconnects to avoid hanging streams in Telegram.
        self.disconnected_chats: Set[int] = set()
        # === VIVENTIUM END ===

        # === VIVENTIUM START ===
        # Optional reconnect grace (seconds) before surfacing a disconnect notice.
        self.reconnect_grace_s: float = float(
            os.getenv("VIVENTIUM_TELEGRAM_RECONNECT_GRACE_S", "5.0").strip() or "5.0"
        )
        # === VIVENTIUM END ===

        # === VIVENTIUM START ===
        # Tail wait for holding/placeholder responses (tools still running).
        self.holding_tail_timeout_s: float = float(
            os.getenv("VIVENTIUM_TELEGRAM_HOLDING_TAIL_TIMEOUT_S", "90.0").strip() or "90.0"
        )
        self.standard_tail_timeout_s: float = float(
            os.getenv("VIVENTIUM_TELEGRAM_TAIL_TIMEOUT_S", "2.0").strip() or "2.0"
        )
        # === VIVENTIUM END ===
        
        # Cleanup task will be started lazily
        self._cleanup_task = None
        # Track which LiveKit rooms we've already confirmed a dispatch exists for.
        # Note: A dispatch existing does NOT guarantee the agent connected (e.g., if no worker was
        # available at the time of dispatch). We use `force=True` re-dispatch when needed.
        self._dispatched_rooms: Set[str] = set()

    def _livekit_api_url(self) -> str:
        """
        Convert LIVEKIT_URL (ws:// / wss://) into an HTTP base URL for LiveKit Server APIs.
        LiveKitAPI uses HTTP/Twirp and does NOT accept ws:// URLs.
        """
        url = (self.url or "").strip()
        if url.startswith("ws://"):
            return "http://" + url[len("ws://") :]
        if url.startswith("wss://"):
            return "https://" + url[len("wss://") :]
        return url

    def _is_agent_participant(self, participant: rtc.RemoteParticipant) -> bool:
        """Return True if the participant represents a LiveKit Agent."""
        try:
            if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
                return True
        except Exception:
            # Ignore and fall back to identity heuristic below
            pass
        # Fallback / compatibility heuristic: many agent identities start with "agent-"
        return participant.identity.startswith("agent")

    async def _ensure_agent_dispatch(self, room_name: str, chat_id: int, *, force: bool = False) -> None:
        """
        Ensure an explicit dispatch exists for this room so the agent worker joins.

        Why: When the agent worker registers with an `agent_name`, LiveKit requires
        explicit dispatch via AgentDispatchService.CreateDispatch.
        """
        if not room_name:
            return
        if not force and room_name in self._dispatched_rooms:
            return
        if not self.api_key or not self.api_secret or not self.url:
            logger.warning("Cannot dispatch agent: missing LiveKit credentials")
            return

        api_url = self._livekit_api_url()
        if not api_url or api_url.startswith("ws"):
            logger.warning("Cannot dispatch agent: invalid LiveKit API URL derived from LIVEKIT_URL=%s", self.url)
            return

        try:
            async with api.LiveKitAPI(url=api_url, api_key=self.api_key, api_secret=self.api_secret) as lkapi:
                existing: List[api.AgentDispatch] = []
                try:
                    # Avoid duplicate dispatches (which can spawn multiple agents in the same room)
                    existing = await lkapi.agent_dispatch.list_dispatch(room_name)
                except Exception as e:
                    # LiveKit API can intermittently return 503 "no response from servers".
                    # We still attempt CreateDispatch as a best-effort fallback.
                    logger.warning(
                        "Failed to list agent dispatches (non-fatal) | room=%s agent=%s force=%s err=%s",
                        room_name,
                        self.agent_name,
                        force,
                        e,
                    )
                    existing = []

                if force:
                    # Force re-dispatch: delete existing dispatches for this agent+room then create a new one.
                    # This recovers from the scenario where a dispatch was created while no worker was
                    # available (LiveKit logs: 'not dispatching agent job since no worker is available').
                    for d in existing:
                        if d.agent_name != self.agent_name:
                            continue
                        try:
                            logger.info(
                                "🧹 Deleting existing agent dispatch before re-dispatch | dispatch_id=%s agent=%s room=%s chat_id=%s",
                                d.id,
                                self.agent_name,
                                room_name,
                                chat_id,
                            )
                            await lkapi.agent_dispatch.delete_dispatch(d.id, room_name)
                        except Exception as e:
                            logger.warning(
                                "Failed to delete agent dispatch (non-fatal) | dispatch_id=%s agent=%s room=%s err=%s",
                                getattr(d, "id", None),
                                self.agent_name,
                                room_name,
                                e,
                            )

                    logger.info(
                        "🚀 Creating agent dispatch (force) | agent=%s room=%s chat_id=%s",
                        self.agent_name,
                        room_name,
                        chat_id,
                    )
                    await lkapi.agent_dispatch.create_dispatch(
                        api.CreateAgentDispatchRequest(
                            agent_name=self.agent_name,
                            room=room_name,
                            metadata=json.dumps({"source": "telegram", "chat_id": str(chat_id)}),
                        )
                    )
                    self._dispatched_rooms.add(room_name)
                    return

                if any(d.agent_name == self.agent_name for d in existing):
                    logger.info(
                        "✅ Agent dispatch already exists | agent=%s room=%s chat_id=%s",
                        self.agent_name,
                        room_name,
                        chat_id,
                    )
                    self._dispatched_rooms.add(room_name)
                    return

                logger.info("🚀 Creating agent dispatch | agent=%s room=%s chat_id=%s", self.agent_name, room_name, chat_id)
                await lkapi.agent_dispatch.create_dispatch(
                    api.CreateAgentDispatchRequest(
                        agent_name=self.agent_name,
                        room=room_name,
                        metadata=json.dumps({"source": "telegram", "chat_id": str(chat_id)}),
                    )
                )
                self._dispatched_rooms.add(room_name)
        except Exception as e:
            logger.warning(
                "Failed to create agent dispatch (non-fatal) | room=%s agent=%s force=%s err=%s",
                room_name,
                self.agent_name,
                force,
                e,
            )

    def _agent_present(self, room: rtc.Room) -> bool:
        """Check if the agent participant is currently present in the room."""
        try:
            return any(self._is_agent_participant(p) for p in room.remote_participants.values())
        except Exception:
            return False

    async def _wait_for_agent(self, chat_id: int, room: rtc.Room, *, timeout: float) -> bool:
        """
        Wait for the agent to connect to the room. Returns True if the agent is present.
        """
        if self._agent_present(room):
            return True

        agent_event = self.agent_connected_events.get(chat_id)
        if not agent_event:
            # Fallback: if we can't wait on the event, just poll once after a short delay.
            await asyncio.sleep(min(0.5, timeout))
            return self._agent_present(room)

        # Clear event to ensure we wait for a NEW connection if it was set previously
        agent_event.clear()
        try:
            await asyncio.wait_for(agent_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return self._agent_present(room)

        # Allow Agent RoomIO to fully subscribe & initialize
        await asyncio.sleep(0.5)
        return True

    def set_on_message_callback(self, callback: Callable[[int, str], Awaitable[None]]):
        """Set a callback to handle proactive messages from the agent."""
        self.on_message_callback = callback

    async def _ensure_cleanup_task(self):
        if self._cleanup_task is None or self._cleanup_task.done():
            # Ensure we have a running loop
            try:
                asyncio.get_running_loop()
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            except RuntimeError:
                pass # No loop yet

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(60)
            now = time.time()
            for chat_id in list(self.rooms.keys()):
                if now - self.last_activity.get(chat_id, 0) > 300: # 5 min timeout
                    await self.disconnect_user(chat_id)

    async def connect_user(self, chat_id: int) -> rtc.Room:
        await self._ensure_cleanup_task()
        self.last_activity[chat_id] = time.time()
        
        if chat_id in self.rooms:
            if self.rooms[chat_id].connection_state == rtc.ConnectionState.CONN_CONNECTED:
                return self.rooms[chat_id]
            else:
                # Stale connection, cleanup
                await self.disconnect_user(chat_id)

        # Generate Token
        # Use a dynamic room name to prevent stale room state issues
        # We append a short timestamp component (minutes since epoch) to rotate rooms occasionally
        # but keep them stable for a short session.
        timestamp_component = int(time.time() / 600) * 600 # Rotate room every 10 mins
        room_name = f"telegram-{chat_id}-{timestamp_component}"
        identity = f"telegram-user-{chat_id}"
        
        token = api.AccessToken(self.api_key, self.api_secret) \
            .with_identity(identity) \
            .with_name(f"Telegram User {chat_id}") \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                # CRITICAL: Do NOT set agent=True here.
                # That would mark the **Telegram user participant** as kind=AGENT, which is incorrect.
                # The real agent is dispatched separately via AgentDispatchService.CreateDispatch.
            )).to_jwt()

        room = rtc.Room()
        queue = asyncio.Queue()
        self.queues[chat_id] = queue

        @room.on("data_received")
        def on_data_received(data: rtc.DataPacket):
            logger.debug(f"Received data packet from {data.topic} (chat_id={chat_id})")
            if data.topic != LK_CHAT_TOPIC:
                logger.debug(f"   Ignoring data packet - wrong topic: {data.topic} (expected {LK_CHAT_TOPIC})")
                return
            try:
                payload = json.loads(data.data.decode("utf-8"))
                if isinstance(payload, dict):
                    message_text = payload.get("message") or payload.get("text")
                    if message_text:
                        logger.info(f"📨 Received chat message (chat_id={chat_id}): {message_text[:80]}...")
                        queue.put_nowait(message_text)
                    else:
                        logger.warning(f"   Data packet has no message/text field: {payload}")
            except Exception as e:
                logger.error(f"Failed to parse chat message (chat_id={chat_id}): {e}")

        @room.on("transcription_received")
        def on_transcription_received(segments, participant, publication):
            """
            LiveKit Agents emit their spoken responses as transcription segments.
            Only push the final transcript once to Telegram to avoid repeated text.
            """
            self._handle_transcription_segments(chat_id, segments)

        # CRITICAL FIX: Track when agent joins so we can wait before sending messages
        # This prevents the race condition where messages are sent before the agent subscribes
        agent_event = asyncio.Event()
        self.agent_connected_events[chat_id] = agent_event
        
        @room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info(f"Participant connected: {participant.identity} in room {room_name}")
            # Prefer participant kind over identity prefix (more reliable)
            if self._is_agent_participant(participant):
                logger.info(f"Agent detected! Setting agent_connected event for chat {chat_id}")
                agent_event.set()
                # === VIVENTIUM START ===
                # Agent present again; clear any disconnect flags.
                self.disconnected_chats.discard(chat_id)
                # === VIVENTIUM END ===

        # === VIVENTIUM START ===
        @room.on("connection_state_changed")
        def on_connection_state_changed(state: rtc.ConnectionState):
            if state == rtc.ConnectionState.CONN_CONNECTED:
                self.disconnected_chats.discard(chat_id)
            elif state == rtc.ConnectionState.CONN_DISCONNECTED:
                self._notify_disconnect(chat_id)

        @room.on("disconnected")
        def on_disconnected(reason: str):
            logger.warning("LiveKit room disconnected | chat_id=%s room=%s reason=%s", chat_id, room_name, reason)
            self._notify_disconnect(chat_id)
        # === VIVENTIUM END ===

        try:
            logger.info(f"Connecting to LiveKit room {room_name}...")
            await room.connect(self.url, token)
            logger.info(f"Connected to room {room_name}")

            # CRITICAL: Ensure agent is explicitly dispatched (required when agent worker uses agent_name)
            await self._ensure_agent_dispatch(room_name=room_name, chat_id=chat_id, force=False)
            
            self.rooms[chat_id] = room
            self.room_names[chat_id] = room_name
        except Exception as e:
            logger.error(f"Failed to connect to LiveKit: {e}")
            raise

        return room

    async def disconnect_user(self, chat_id: int):
        if chat_id in self.rooms:
            logger.info(f"Disconnecting user {chat_id}")
            await self.rooms[chat_id].disconnect()
            del self.rooms[chat_id]
        # === VIVENTIUM START ===
        self.disconnected_chats.discard(chat_id)
        # === VIVENTIUM END ===
        if chat_id in self.room_names:
            del self.room_names[chat_id]
        if chat_id in self.queues:
            del self.queues[chat_id]
        if chat_id in self.last_activity:
            del self.last_activity[chat_id]
        if chat_id in self.agent_connected_events:
            del self.agent_connected_events[chat_id]

    async def send_message(self, chat_id: int, text: str):
        self.last_activity[chat_id] = time.time()
        room = await self.connect_user(chat_id)
        room_name = self.room_names.get(chat_id) or getattr(room, "name", "") or ""

        # Reset transcription dedupe so the next turn can stream even if the
        # conscious reply matches the previous one verbatim.
        self._reset_transcription_state(chat_id)
        
        # CRITICAL: Never send the user message until the agent is actually in the room.
        # LiveKit data/text messages are not persisted; if we send before the agent joins,
        # the agent will miss the message and Telegram will time out.
        #
        # We also handle the common startup race:
        # - Telegram creates the dispatch while the worker is still starting
        # - LiveKit logs: "not dispatching agent job since no worker is available"
        # In that case, we force a re-dispatch (delete+recreate) once we notice the agent never joined.

        # Ensure we requested a dispatch for this room (connect_user already does this, but it can be skipped
        # if credentials were missing at that time).
        if room_name:
            await self._ensure_agent_dispatch(room_name=room_name, chat_id=chat_id, force=False)

        # Wait + re-dispatch retries
        if not self._agent_present(room):
            logger.info("Agent not present in room telegram-%s, waiting for agent to join...", chat_id)

            # First wait: give the worker time to register (esp. during startup)
            if not await self._wait_for_agent(chat_id, room, timeout=20.0):
                logger.warning(
                    "Agent still not connected after initial wait | chat_id=%s room=%s -> forcing re-dispatch",
                    chat_id,
                    room_name or f"telegram-{chat_id}",
                )
                if room_name:
                    await self._ensure_agent_dispatch(room_name=room_name, chat_id=chat_id, force=True)

                # Second wait: after re-dispatch, wait longer for job assignment + connect
                if not await self._wait_for_agent(chat_id, room, timeout=30.0):
                    logger.error(
                        "Agent did not connect after re-dispatch | chat_id=%s room=%s",
                        chat_id,
                        room_name or f"telegram-{chat_id}",
                    )
                    raise RuntimeError("Agent did not connect to the LiveKit room")
        else:
            logger.debug("Agent present in room telegram-%s, sending message", chat_id)
            # Small stability delay
            await asyncio.sleep(0.2)
        
        # CRITICAL FIX: Use send_text() instead of publish_data()
        # LiveKit Agents use register_text_stream_handler(TOPIC_CHAT) which expects
        # text streams, not raw data packets. The agent's RoomIO._on_user_text_input
        # only fires when a text stream is received on the "lk.chat" topic.
        try:
            # Log participant info before sending
            agent_participants = [p.identity for p in room.remote_participants.values() if p.identity.startswith("agent")]
            logger.debug(f"   Agent participants before send: {agent_participants}")
            logger.debug(f"   Total remote participants: {len(room.remote_participants)}")
            
            await room.local_participant.send_text(
                text,
                topic=LK_CHAT_TOPIC,
            )
            logger.info(f"✅ Sent text stream to room telegram-{chat_id}: {text[:50]}...")
            logger.debug(f"   Full message: {text}")
            logger.debug(f"   Topic: {LK_CHAT_TOPIC}, Room participants: {len(room.remote_participants)}")
        except Exception as e:
            logger.error(f"❌ Failed to send text stream to room telegram-{chat_id}: {e}")
            raise

    async def chat_stream(self, text: str, convo_id: str, **kwargs) -> AsyncIterator[str]:
        """
        Mimics the robot.ask_stream_async signature.
        convo_id is the chat_id.
        """
        try:
            chat_id = int(convo_id)
        except ValueError:
            logger.error(f"Invalid chat_id {convo_id}")
            return

        # Mark this chat as active
        self.active_chats.add(chat_id)

        try:
            logger.info(f"🚀 Starting chat_stream for chat_id={chat_id}, text={text[:50]}...")
            try:
                await self.send_message(chat_id, text)
            except Exception as e:
                logger.exception("Failed to deliver message to agent (chat_id=%s): %s", chat_id, e)
                yield "\n\n(⚠️ Agent connection failed. Please check if the agent is running.)"
                return
            logger.info(f"✅ Message sent, waiting for response (chat_id={chat_id})...")
            
            queue = self.queues[chat_id]
            logger.debug(f"   Queue size before draining: {queue.qsize()}")
            
            # Yield responses
            # We need a way to stop. For now, we yield what we get.
            # The Bot usually expects a stream.
            # If we get a full message, we yield it.
            while not queue.empty():
                stale_chunk = await queue.get()
                logger.debug(
                    "Draining stale chunk before streaming | chat=%s len=%d preview=\"%s\"",
                    chat_id,
                    len(stale_chunk),
                    (stale_chunk.replace("\n", " "))[:120],
                )
            
            start_time = time.time()
            response_received = False
            
            logger.info(f"⏳ Waiting for agent response (chat_id={chat_id}, timeout=60s)...")
            
            room = self.rooms.get(chat_id)
            while True:
                # === VIVENTIUM START ===
                if self._is_room_disconnected(chat_id, room):
                    # Give LiveKit a short grace window to recover mid-stream.
                    if await self._wait_for_reconnect(chat_id, room, self.reconnect_grace_s):
                        continue
                    notice = self._get_connection_lost_notice()
                    if notice:
                        yield f"\n\n(⚠️ {notice})"
                    break
                # === VIVENTIUM END ===
                try:
                    # Wait for response
                    # If we haven't received anything yet, wait longer (agent thinking)
                    timeout = 60.0 if not response_received else 5.0
                    
                    logger.debug(f"   Waiting for queue.get() (chat_id={chat_id}, timeout={timeout}s, queue_size={queue.qsize()})...")
                    chunk = await asyncio.wait_for(queue.get(), timeout=timeout)
                    response_received = True
                    logger.info(
                        "📥 Streaming agent chunk | chat=%s len=%d preview=\"%s\"",
                        chat_id,
                        len(chunk),
                        (chunk.replace("\n", " "))[:120],
                    )
                    yield chunk
                    
                    # If the queue is empty after a short delay, maybe we are done?
                    # This is tricky with streams.
                    # For now, assume 1 message response per prompt.
                    if queue.empty():
                        # Smart Timeout Logic:
                        # If the message looks like a "holding" or "thinking" message, wait much longer
                        # for the subconscious insight to arrive.
                        # Otherwise, use a standard tail timeout.
                        
                        chunk_lower = chunk.lower().strip() if chunk else ""
                        is_holding_message = self._is_holding_message(chunk or "")

                        tail_timeout = (
                            self.holding_tail_timeout_s
                            if is_holding_message
                            else self.standard_tail_timeout_s
                        )
                        
                        if is_holding_message:
                            logger.info(
                                "Detected holding message ('%s'), extending stream timeout to %.1fs for insights", 
                                (chunk or "")[:50], 
                                tail_timeout
                            )
                        
                        try:
                            extra_chunk = await asyncio.wait_for(queue.get(), timeout=tail_timeout)
                            logger.info(
                                "Streaming additional agent chunk | chat=%s len=%d preview=\"%s\"",
                                chat_id,
                                len(extra_chunk),
                                (extra_chunk.replace("\n", " "))[:120],
                            )
                            yield extra_chunk
                            continue
                        except asyncio.TimeoutError:
                            # === VIVENTIUM START ===
                            if self._is_room_disconnected(chat_id, room):
                                if await self._wait_for_reconnect(chat_id, room, self.reconnect_grace_s):
                                    continue
                                notice = self._get_connection_lost_notice()
                                if notice:
                                    yield f"\n\n(⚠️ {notice})"
                            # === VIVENTIUM END ===
                            logger.debug("No more chunks from agent | chat=%s", chat_id)
                            break
                            
                except asyncio.TimeoutError:
                    if not response_received:
                        logger.warning(
                            "Agent response pending | chat=%s timeout=%.1fs (no chunks yet) - Aborting",
                            chat_id,
                            timeout,
                        )
                        yield "\n\n(⚠️ Agent connection timed out. Please check if the agent is running.)"
                        break
                        # continue # Keep waiting?
                    logger.debug(
                        "Agent stream idle timeout after receiving chunks | chat=%s",
                        chat_id,
                    )
                    break
        finally:
            # Mark chat as inactive so proactive messages can be routed via callback
            self.active_chats.discard(chat_id)
                
    # Alias for bot compatibility
    ask_stream_async = chat_stream

    # Methods to satisfy the Bot's expected interface for 'robot'
    def reset(self, convo_id, system_prompt=None):
        # REMOVED: system_prompt parameter - Viventium handles system prompts, not the bridge
        # No-op or maybe disconnect room?
        # asyncio.create_task(self.disconnect_user(int(convo_id)))
        pass

    # REMOVED: conversation property - No longer used after removing tool_calls check
    # REMOVED: tokens_usage property - No longer used after removing from update_info_message

    # Internal helpers -------------------------------------------------
    def _segment_attr(self, segment: Any, names: List[str]):
        if not segment:
            return None
        if isinstance(segment, dict):
            for name in names:
                if name in segment:
                    return segment[name]
        else:
            for name in names:
                if hasattr(segment, name):
                    return getattr(segment, name)
        return None

    def _handle_transcription_segments(self, chat_id: int, segments: List[Any]) -> None:
        if not segments:
            return

        text_chunks: List[str] = []
        final_flags: List[bool] = []
        for segment in segments:
            text = self._segment_attr(segment, ["text", "text_normalized"])
            if text:
                text_chunks.append(str(text).strip())
            final_flags.append(bool(self._segment_attr(segment, ["final", "is_final"])))

        if not text_chunks:
            return

        message_text = " ".join(chunk for chunk in text_chunks if chunk).strip()
        if not message_text:
            return

        state = self.transcription_state.setdefault(chat_id, {"last_final": "", "last_partial": ""})
        state["last_partial"] = message_text

        if not any(final_flags):
            return  # still streaming partial text

        if message_text == state.get("last_final"):
            return  # duplicate final event

        state["last_final"] = message_text
        
        # CRITICAL FIX: Filter out internal function calls and system artifacts
        # The LLM sometimes emits function call XML that should NOT be shown to users
        if self._is_internal_message(message_text):
            logger.debug(
                "Filtered internal message (function call/artifact) | chat_id=%s preview=\"%s\"",
                chat_id,
                message_text[:120],
            )
            return
        
        queue = self.queues.get(chat_id)
        if queue:
            # If chat is active (waiting for response), put in queue
            if chat_id in self.active_chats:
                logger.info(f"Received transcription for active chat: {message_text[:80]}...")
                queue.put_nowait(message_text)
            # If chat is inactive (proactive message), try callback
            elif self.on_message_callback:
                logger.info(f"Received PROACTIVE message for inactive chat: {message_text[:80]}...")
                if asyncio.iscoroutinefunction(self.on_message_callback):
                    asyncio.create_task(self.on_message_callback(chat_id, message_text))
                else:
                    # Warning: Synchronous callback might block
                    self.on_message_callback(chat_id, message_text)
            else:
                # Fallback: put in queue anyway (might be picked up next time)
                logger.info(f"Received message for inactive chat (no callback): {message_text[:80]}...")
                queue.put_nowait(message_text)

    def _reset_transcription_state(self, chat_id: int) -> None:
        # CRITICAL: Must also clear the queue for this chat_id to prevent stale messages
        if chat_id in self.queues:
            q = self.queues[chat_id]
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break
        self.transcription_state[chat_id] = {"last_final": "", "last_partial": ""}

    # === VIVENTIUM START ===
    def _get_connection_lost_notice(self) -> str:
        return os.getenv(
            "VIVENTIUM_TELEGRAM_CONNECTION_LOST_MESSAGE",
            "Connection lost while working. Please retry.",
        ).strip()

    def _notify_disconnect(self, chat_id: int) -> None:
        self.disconnected_chats.add(chat_id)
        queue = self.queues.get(chat_id)
        if queue and chat_id in self.active_chats:
            notice = self._get_connection_lost_notice()
            if notice:
                queue.put_nowait(f"\n\n(⚠️ {notice})")

    def _is_room_disconnected(self, chat_id: int, room: Optional[rtc.Room]) -> bool:
        if chat_id in self.disconnected_chats:
            return True
        if room is None:
            return False
        try:
            return room.connection_state == rtc.ConnectionState.CONN_DISCONNECTED
        except Exception:
            return False

    async def _wait_for_reconnect(self, chat_id: int, room: Optional[rtc.Room], timeout_s: float) -> bool:
        if timeout_s <= 0:
            return False
        if room is None:
            return False
        start = time.time()
        while time.time() - start < timeout_s:
            if not self._is_room_disconnected(chat_id, room):
                return True
            await asyncio.sleep(0.25)
        return False
    # === VIVENTIUM END ===

    def _is_holding_message(self, text: str) -> bool:
        if not text:
            return False

        normalized = " ".join(text.lower().strip().split())
        if not normalized:
            return False

        holding_phrases = (
            "hang on",
            "one moment",
            "give me a sec",
            "just a sec",
            "stand by",
            "let me get",
            "let me pull",
            "let me fetch",
            "let me grab",
            "let me check",
            "let me look up",
            "let me retrieve",
            "getting the full",
            "getting the details",
            "pulling up",
            "checking",
            "working on it",
            "fetching",
        )

        if any(phrase in normalized for phrase in holding_phrases):
            return True
        if (normalized.endswith("...") or normalized.endswith(":")) and len(normalized) < 220:
            return True
        return False

    def _is_internal_message(self, text: str) -> bool:
        """
        Check if a message is an internal system artifact that should NOT be shown to users.
        
        This filters out:
        - Function call XML tags from xAI/Grok LLM (e.g., <xai:function_call>)
        - Internal system markers (e.g., {no-response}, <!--viv_internal:brew_begin-->)
        - Empty or whitespace-only messages
        """
        if not text or not text.strip():
            return True
        
        text_stripped = text.strip()
        
        # Filter xAI/Grok function call XML format
        if text_stripped.startswith("<xai:function_call") or "<xai:function_call" in text_stripped:
            return True
        
        # Filter generic XML-style function calls
        if text_stripped.startswith("<function_call") or "<function_call" in text_stripped:
            return True
        
        # Filter internal system markers
        internal_markers = [
            "{no-response}",
            "{{no-response}}",
            "<!--viv_internal:brew_begin-->",
            "<!--viv_internal:brew_end-->",
            # Legacy markers (kept for backward compatibility)
            "{DEEP_THINKING_ACTIVATED}",
            "{{DEEP_THINKING_ACTIVATED}}",
        ]
        for marker in internal_markers:
            if marker in text_stripped:
                return True
        
        # Filter messages that are ONLY XML tags (no actual content)
        if text_stripped.startswith("<") and text_stripped.endswith(">"):
            return True
        
        return False
