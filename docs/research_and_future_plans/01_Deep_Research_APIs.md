# Deep Research APIs - Configuration Research

**Purpose**: Research document consolidating findings on Deep Research APIs from major providers (OpenAI, Google, Perplexity) and their integration potential with LibreChat. This is a future plan for enhancing Viventium's research capabilities.

**Status**: Research Complete | Implementation: Pending Decision  
**Last Updated**: 2026-01-16

---

## 📋 Executive Summary

Deep Research APIs provide autonomous, multi-step research capabilities that:
- Plan research strategies autonomously
- Search the web comprehensively
- Synthesize findings into cited reports
- Take minutes (not seconds) to produce comprehensive results

This document evaluates three providers and their LibreChat compatibility.

---

## 🔍 Provider Analysis

### 1. OpenAI Deep Research (Responses API)

| Aspect | Details |
|--------|---------|
| **Models** | `o3-deep-research`, `o4-mini-deep-research` |
| **API** | Responses API (`/v1/responses`) |
| **LibreChat Support** | ✅ **Yes** - via `useResponsesApi: true` |
| **Configuration Type** | Config-only (no code changes) |
| **Status** | Ready for implementation |

#### Key Findings
- OpenAI's Deep Research uses the **Responses API** which LibreChat supports
- The `useResponsesApi: true` flag in modelSpecs routes requests correctly
- Models support web search, file search, and MCP tools
- Long-running tasks supported via `background: true` mode

#### Configuration Parameters
| Parameter | Values | Description |
|-----------|--------|-------------|
| `useResponsesApi` | `true` / `false` | Routes to `/v1/responses` |
| `verbosity` | `low` / `medium` / `high` | Output detail level |
| `web_search` | `true` / `false` | Enables web search tool |
| `reasoning_effort` | `low` / `medium` / `high` | Depth of reasoning |
| `reasoning_summary` | `concise` / `detailed` | Reasoning format |

#### LibreChat Configuration (Ready to Use)
```yaml
modelSpecs:
  list:
    # VIVENTIUM START
    # Purpose: OpenAI Deep Research via Responses API
    # VIVENTIUM END
    - name: "o3-deep-research"
      label: "o3 Deep Research"
      description: "Comprehensive research with web search & citations"
      group: "OpenAI"
      groupIcon: "openAI"
      iconURL: "openAI"
      preset:
        endpoint: "openAI"
        model: "o3-deep-research"
        useResponsesApi: true
        modelLabel: "o3 Deep Research"
        verbosity: "medium"

    - name: "o4-mini-deep-research"
      label: "o4 Mini Deep Research"
      description: "Fast, cost-effective deep research"
      group: "OpenAI"
      groupIcon: "openAI"
      iconURL: "openAI"
      preset:
        endpoint: "openAI"
        model: "o4-mini-deep-research"
        useResponsesApi: true
        modelLabel: "o4 Mini Deep Research"
        verbosity: "low"
```

#### Important Notes
- **Prompting**: API version does NOT auto-clarify questions (unlike ChatGPT UI)
- **Runtime**: Can take several minutes for comprehensive research
- **Snapshots**: Pin specific versions for reproducibility (e.g., `o3-deep-research-2025-06-26`)

#### References
- [OpenAI Deep Research Guide](https://platform.openai.com/docs/guides/deep-research)
- [Responses API Reference](https://platform.openai.com/docs/api-reference/responses)
- [LibreChat modelSpecs Docs](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/model_specs)

---

### 2. Google Gemini Deep Research (Interactions API)

| Aspect | Details |
|--------|---------|
| **Agent** | `deep-research-pro-preview-12-2025` |
| **API** | Interactions API (`/v1beta/interactions`) |
| **LibreChat Support** | ❌ **No** - Requires code changes |
| **Configuration Type** | Code changes required |
| **Status** | Not feasible without development |

#### Key Findings
- Google's Deep Research is NOT a model - it's an **agent**
- Uses completely different API pattern (Interactions API vs generateContent)
- Requires async job handling with polling
- LibreChat only supports `generateContent` for Google endpoint

#### API Comparison
| Aspect | Standard Gemini | Deep Research Agent |
|--------|----------------|---------------------|
| **Endpoint** | `POST /v1beta/models/{model}:generateContent` | `POST /v1beta/interactions` |
| **Pattern** | Synchronous request/response | Async (long-running with polling) |
| **Identifier** | Model name | Agent: `deep-research-pro-preview-12-2025` |
| **Required** | N/A | `background: true` |

#### Why Config-Only Won't Work
1. Different HTTP endpoint path
2. Requires polling/streaming for async results
3. Agent parameter not supported in LibreChat Google endpoint
4. LibreChat expects synchronous request/response

#### Workaround Options
1. **Custom Proxy/Middleware**: Build service that wraps Interactions API as chat completion
2. **Actions (OpenAPI)**: Create OpenAPI spec for an Agent Action that calls Interactions API
3. **Wait for LibreChat**: Future versions may add Interactions API support

#### References
- [Gemini Deep Research Agent Guide](https://ai.google.dev/gemini-api/docs/deep-research)
- [Interactions API Reference](https://ai.google.dev/api/interactions-api)
- [LibreChat Google Docs](https://www.librechat.ai/docs/configuration/pre_configured_ai/google)

---

### 3. Perplexity Deep Research (Already Configured)

| Aspect | Details |
|--------|---------|
| **Model** | `sonar-deep-research` |
| **API** | Standard chat completion |
| **LibreChat Support** | ✅ **Yes** - Already configured |
| **Configuration Type** | Config-only |
| **Status** | ✅ Active in `librechat.yaml` |

#### Current Configuration (Lines 406-428)
```yaml
- name: "perplexity"
  apiKey: "${PERPLEXITY_API_KEY}"
  baseURL: "https://api.perplexity.ai/"
  models:
    default: [
      "sonar-deep-research",  # Deep research with web access
      "sonar-reasoning-pro",
      "sonar-reasoning",
      "sonar-pro",
      "sonar",
      "r1-1776"
    ]
```

#### Advantages
- Already working in production
- Standard API (no special handling needed)
- Cost-effective compared to OpenAI o3-family
- Fast response times

---

## 📊 Provider Comparison Matrix

| Feature | OpenAI Deep Research | Google Deep Research | Perplexity |
|---------|---------------------|---------------------|------------|
| **LibreChat Support** | ✅ Config-only | ❌ Code required | ✅ Config-only |
| **API Type** | Responses API | Interactions API | Chat Completion |
| **Implementation Effort** | Low | High | None (done) |
| **Run Time** | Minutes | Minutes | Faster |
| **Cost** | Higher (o3 pricing) | Standard | Lower |
| **Citations** | Inline | Inline | Inline |
| **Web Search** | Built-in | Built-in | Built-in |

---

## 🎯 Recommendations

### Immediate (No Development Required)
1. **Continue using Perplexity `sonar-deep-research`** - Already configured and working
2. **Add OpenAI Deep Research models** - Config-only, ready to implement

### Future Consideration
1. **Google Deep Research** - Wait for LibreChat native support or build custom middleware
2. **Evaluate costs** - o3-family pricing vs Perplexity for research use cases

---

## 📝 Implementation Checklist

### For OpenAI Deep Research (When Ready to Implement)
- [ ] Verify OpenAI account has access to `o3-deep-research` / `o4-mini-deep-research`
- [ ] Add `openAI` to `addedEndpoints` in `librechat.yaml`
- [ ] Add modelSpecs entries from this document
- [ ] Test with sample research queries
- [ ] Document usage guidelines for users

### For Google Deep Research (Future)
- [ ] Monitor LibreChat releases for Interactions API support
- [ ] OR: Design custom middleware/proxy architecture
- [ ] Evaluate development effort vs. benefit

---

## 🔗 Reference Links

### Official Documentation
- [OpenAI Deep Research Guide](https://platform.openai.com/docs/guides/deep-research)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [Google Gemini Deep Research](https://ai.google.dev/gemini-api/docs/deep-research)
- [Google Interactions API](https://ai.google.dev/api/interactions-api)
- [Perplexity API Docs](https://docs.perplexity.ai/)

### LibreChat Documentation
- [LibreChat modelSpecs](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/model_specs)
- [LibreChat OpenAI Setup](https://www.librechat.ai/docs/configuration/pre_configured_ai/openai)
- [LibreChat Google Setup](https://www.librechat.ai/docs/configuration/pre_configured_ai/google)

---

## 📅 Research Timeline

| Date | Activity |
|------|----------|
| 2026-01-16 | Initial research completed |
| TBD | OpenAI Deep Research implementation decision |
| TBD | Google Deep Research feasibility review |

---

**Note**: This document should be updated when:
- LibreChat adds new API support
- Provider APIs change significantly
- Implementation decisions are made
- New deep research providers emerge
