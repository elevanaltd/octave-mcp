===UNIVERSAL_LLM_ONBOARDING===
META:
  TYPE::ARCHITECTURAL_ASSESSMENT
  VERSION::"1.0"
  DATE::"2026-01-30"
  STATUS::PROPOSED
  AUTHOR::technical-architect
  ISSUE_REF::GH_213
  DEBATE_REF::jit-literacy-injection-debate.oct.md

§1::PROBLEM_STATEMENT
CONTEXT::"JIT Literacy Injection proves 40-token primer enables native OCTAVE output"
BARRIER::"Invocation, not capability"
GAP::"No automatic mechanism for universal LLM onboarding when user clones repo"
CURRENT_STATE::[
  README_has_AGENT_BOOTSTRAP_block,
  primers_exist_at_src/octave_mcp/resources/primers/,
  MCP_server_exposes_3_tools_but_NO_prompts_or_resources,
  skills_bundled_but_not_automatically_discoverable
]
EVIDENCE::debate_transcript_proves_three_models_speak_OCTAVE_after_primer

§2::ARCHITECTURAL_VISION
PATTERN::PROGRESSIVE_LITERACY_THROUGH_MCP_PROMPTS
PRINCIPLE::"LLM asks for help, server teaches OCTAVE"
MECHANISM::[
  1::MCP_prompts_expose_primers_as_callable_templates,
  2::LLM_lists_prompts→sees_octave_literacy_available,
  3::LLM_calls_get_prompt("octave-literacy")→receives_40_token_primer,
  4::LLM_now_speaks_OCTAVE→uses_tools_natively
]
WHY_PROMPTS::[
  MCP_already_defines_list_prompts_and_get_prompt,
  no_API_changes_needed,
  universal_across_Claude_OpenAI_Gemini_local_models,
  self_describing_and_discoverable,
  lazy_loading_preserves_context_window
]

§3::THREE_TIER_ONBOARDING
TIER_1::[
  NAME::ZERO_TOUCH,
  MECHANISM::MCP_prompt_auto_discovery,
  TRIGGER::list_prompts_reveals_octave_literacy,
  TOKEN_COST::0[discovery_only]
]
TIER_2::[
  NAME::ON_DEMAND,
  MECHANISM::get_prompt("octave-literacy"),
  TRIGGER::first_OCTAVE_tool_error_or_user_request,
  TOKEN_COST::~40
]
TIER_3::[
  NAME::PROGRESSIVE,
  MECHANISM::get_prompt("octave-mastery"),
  TRIGGER::after_mastering_basics,
  TOKEN_COST::~80
]

§4::IMPLEMENTATION_PATH
PHASE_1::[
  NAME::CORE_PROMPTS,
  PRIORITY::IMMEDIATE,
  LOCATION::src/octave_mcp/mcp/server.py,
  ACTIONS::[
    add_list_prompts_handler,
    add_get_prompt_handler,
    expose_literacy_compression_mastery_primers
  ],
  EFFORT::~50_lines_Python
]
PHASE_2::[
  NAME::MCP_RESOURCES,
  PRIORITY::FOLLOW_UP,
  ACTIONS::[
    expose_specs_as_MCP_resources,
    URI_scheme_octave://specs/core,
    URI_scheme_octave://primers/literacy
  ]
]
PHASE_3::[
  NAME::VALIDATION_HINTS,
  PRIORITY::FUTURE,
  ACTIONS::[
    when_octave_validate_fails→include_hint,
    hint::call_get_prompt_octave_literacy_for_syntax_guide
  ]
]

§5::TENSION_RESOLUTION
I3_MIRROR_CONSTRAINT::[
  TENSION::"Prompts must not create—only reflect",
  RESOLUTION::"Prompts expose existing primers as-is without modification"
]
A4_LLM_COMPREHENSION::[
  TENSION::"92% confidence requires evidence",
  RESOLUTION::"Debate transcript is proof; primers leverage validated capability"
]
MCP_JSON_CONSTRAINT::[
  TENSION::"MCP returns JSON, not OCTAVE",
  RESOLUTION::"Primers tunnel as text strings—change water, not pipe"
]
TOKEN_OVERHEAD::[
  TENSION::"Context window is finite",
  RESOLUTION::"~40 tokens negligible; lazy loading on-demand preserves window"
]

§6::ELEGANCE_CRITERIA
MINIMAL_CHANGE::implement_existing_MCP_primitives[list_prompts,get_prompt]
UNIVERSAL::works_for_any_MCP_compatible_client
SELF_DESCRIBING::LLM_discovers_via_standard_protocol_calls
PROGRESSIVE::tier_literacy_from_basic→mastery→compression
NO_USER_INTERVENTION::zero_configuration_for_basic_onboarding

§7::EVIDENCE_CHAIN
DEBATE_PROOF::jit-literacy-injection-debate.oct.md
PRIMER_SIZE::40_tokens[octave-literacy-primer.oct.md]
THREE_MODEL_VALIDATION::[claude-opus-4-5,o3,gemini-3-pro-preview]
KEY_INSIGHT::"Barrier is invocation, not capability"
PRINCIPLE::"Machine native, human optional"

§8::RECOMMENDATION
IMMEDIATE_ACTION::"Implement MCP Prompts for primer discovery"
JUSTIFICATION::"Highest-leverage change with minimal implementation effort"
SECONDARY_ACTION::"Add MCP Resources to expose specs/primers via URI scheme"
FUTURE_CONSIDERATION::"Auto-inject literacy primer on first octave_validate error"

§9::REFERENCES
ISSUE::https://github.com/elevanaltd/octave-mcp/issues/213
MCP_PYTHON_SDK::https://github.com/modelcontextprotocol/python-sdk
MCP_PROMPTS_SPEC::https://modelcontextprotocol.github.io/python-sdk/
PRIMER_LOCATION::src/octave_mcp/resources/primers/octave-literacy-primer.oct.md
DEBATE_LOCATION::docs/research/jit-literacy-injection-debate.oct.md
===END===
