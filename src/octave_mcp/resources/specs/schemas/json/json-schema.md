# OCTAVE JSON Schema

This document defines a standardized schema for implementing OCTAVE as JSON, enabling developers to integrate the semantic specification into JSON-based systems while preserving core OCTAVE concepts.

## Table of Contents

- [Introduction](#introduction)
- [Schema Structure](#schema-structure)
- [Core Schema Components](#core-schema-components)
  - [Metadata Object](#metadata-object)
  - [Definitions Object](#definitions-object)
  - [System State Object](#system-state-object)
  - [Domains Array/Object](#domains-arrayobject)
  - [Events Array](#events-array)
  - [Patterns Object](#patterns-object)
  - [Optional Components](#optional-components)
- [Schema Implementation Tiers](#schema-implementation-tiers)
- [Validation Rules](#validation-rules)
- [Implementation Guidelines](#implementation-guidelines)
- [Examples](#examples)
- [JSON Schema Definition](#json-schema-definition)
- [Schema Versioning](#schema-versioning)

## Introduction

The OCTAVE semantic specification can be effectively implemented in JSON format, leveraging JSON's widespread adoption in modern systems while preserving OCTAVE's semantic richness. This JSON schema provides a standardized way to structure OCTAVE concepts while maintaining compatibility with JSON tooling.

Key benefits of implementing OCTAVE as JSON include:
- Use of existing JSON processing libraries
- Integration with JSON-based APIs and data stores
- Familiar syntax for developers
- Strong schema validation capabilities
- Clear serialization/deserialization pathways

This document defines both the conceptual schema and provides a formal JSON Schema definition for validation.

## Schema Structure

An OCTAVE JSON document follows this high-level structure:

```json
{
  "octave": {                  // Root container - required
    "version": "6.0.0",          // OCTAVE version - recommended
    "metadata": { ... },       // Document metadata - optional
    "definitions": { ... },    // Pattern and status definitions - required
    "system": { ... },         // System state information - required
    "domains": { ... },        // Component domains - required
    "events": [ ... ],         // System events - optional
    "patterns": { ... },       // Pattern instances and relationships - optional
    "recommendations": [ ... ] // Actions or recommendations - optional
  }
}
```

Alternatively, a more compact top-level structure can be used for specific applications:

```json
{
  "metadata": { ... },
  "definitions": { ... },
  "system_state": { ... },
  "domains": [ ... ],
  "events": [ ... ],
  "patterns": { ... },
  "relationships": [ ... ],
  "performance_analysis": { ... }
}
```

## Core Schema Components

### Metadata Object

The metadata object contains information about the document itself:

```json
"metadata": {
  "timestamp": "2025-04-21T14:30:00Z",  // ISO 8601 timestamp
  "source": "System Monitoring Service", // Source system
  "implementation": "JSON",             // Implementation format
  "title": "Optional document title",    // Human-readable title
  "license": "CC BY-NC 4.0",            // Optional license information
  "schema_version": "1.0"               // JSON Schema version (recommended)
}
```

### Definitions Object

The definitions object contains pattern and status definitions - required for semantic clarity:

```json
"definitions": {
  "patterns": {
    "RESOURCE-BOTTLENECK": "Resource constraint causing degradation",
    "OLYMPIAN-CASCADE": "Multiple systems failing in sequence"
  },
  "statuses": {
    "RECOVERING": "System rebuilding capacity after significant strain",
    "LEARNING": "System actively adapting to new conditions"
  }
}
```

All patterns referenced in the document must be defined here. This is essential for maintaining the self-documenting nature of OCTAVE.

### System State Object

The system state object represents the overall state, with progression indicated by an array:

```json
"system": {
  "state": ["NRM", "WARN", "DEG"],  // Progression of states
  "progression": true,              // Whether progression is relevant
  "timestamp": "2025-04-21T14:30:00Z" // When the state was recorded
}
```

Alternatively, for compact format:

```json
"system_state": {
  "progression": ["NORMAL", "WARNING", "DEGRADED"],
  "current": "DEGRADED",
  "timestamp": "2025-04-21T14:30:00Z"
}
```

The state values should be consistent with those used elsewhere in the document. Standard status codes (NRM, WARN, DEG, CRIT, FAIL) should be used unless custom statuses are defined in the definitions section.

### Domains Array/Object

Domains can be represented either as a nested object (standard) or an array (compact):

Standard format:
```json
"domains": {
  "compute": {
    "description": "Computing infrastructure components",
    "mythological_reference": "Zeus's Realm",  // Optional but valuable for semantic compression
    "components": {
      "server.node_1": {
        "alias": "N1",
        "metrics": {
          "CPU": {
            "values": [45, 68, 94],  // Progression represented as array
            "unit": "%",             // Optional unit
            "context": "exponential growth"  // Optional context annotation
          },
          "MEMORY": {
            "values": [62, 72, 84],
            "unit": "%",
            "context": "steady increase"
          }
        },
        "status": "DEG"  // Component status
      }
    }
  }
}
```

Compact format:
```json
"domains": [
  {
    "name": "Compute Resources",
    "category": "Infrastructure",
    "components": [
      {
        "name": "server.cluster_primary",
        "alias": "ZC-P",
        "metrics": {
          "CPU": {
            "values": [65, 82, 94, 78],
            "unit": "%",
            "context": "exponential growth, recovery initiated"
          }
        },
        "status": "RECOVERING"
      }
    ]
  }
]
```

### Events Array

Events represent significant occurrences with timestamps:

```json
"events": [
  {
    "code": "DB-IDX",
    "timestamp": "2025-04-21T07:45:00Z",
    "description": "Database index rebuild started"
  },
  {
    "code": "APP-DEPL",
    "timestamp": "2025-04-21T08:12:36Z",
    "description": "Deployment v4.2.7"
  }
]
```

Event codes should be consistent when referenced in relationship chains or other parts of the document.

### Patterns Object

The patterns object contains active patterns and their relationships:

```json
"patterns": {
  "active": ["RESOURCE-BOTTLENECK", "OLYMPIAN-CASCADE"],
  "relationships": [
    {
      "type": "causal",  // Relationship type
      "chain": [         // Causal chain (equivalent to REL: in native format)
        {
          "component": "DB-IDX",
          "effect": "schema_lock"
        },
        {
          "component": "DB1",
          "effect": "query_strain"
        },
        {
          "component": "N1",
          "effect": "cpu_spike"
        },
        {
          "component": "USR",
          "effect": "timeout"
        }
      ]
    },
    {
      "type": "bidirectional",  // Another relationship type
      "components": [
        {
          "component": "N1",
          "effect": "workload_sharing"
        },
        {
          "component": "N2",
          "effect": "failover_support"
        }
      ]
    }
  ]
}
```

Alternative compact format:

```json
"relationships": [
  {
    "type": "causality",
    "sequence": [
      {
        "component": "DB-IDX",
        "effect": "scheduled_task"
      },
      {
        "component": "PD-I",
        "effect": "resource_strain"
      }
    ]
  }
]
```

Every pattern listed in the `active` array must be defined in the `definitions.patterns` object. Every component referenced should exist in the domains section.

### Optional Components

Additional objects can be included for specific applications:

```json
"recommendations": [
  {
    "action": "SCALE-UP",
    "target": "database.primary",
    "priority": "high",
    "expected_impact": "Reduce connection saturation and query latency"
  }
]
```

```json
"performance_analysis": {
  "incident_duration": {
    "value": 15,
    "unit": "min",
    "context": "detection to stability"
  },
  "recovery_effectiveness": {
    "value": 92,
    "unit": "%",
    "context": "service restoration percentage"
  }
}
```

## Schema Implementation Tiers

Similar to native OCTAVE, the JSON schema supports different implementation tiers:

### Tier 1 (Simple)

Basic status reporting with minimal structure:

```json
{
  "octave": {
    "definitions": {
      "patterns": {
        "RESOURCE-ALERT": "Resource threshold breach"
      }
    },
    "system": {
      "state": ["WARN"],
      "timestamp": "2025-04-21T14:30:00Z"
    },
    "domains": {
      "compute": {
        "components": {
          "server.node_1": {
            "metrics": {
              "CPU": {
                "values": [82],
                "unit": "%",
                "context": "near threshold"
              }
            },
            "status": "WARN"
          }
        }
      }
    }
  }
}
```

### Tier 2 (Standard)

Multiple components with relationships:

```json
{
  "octave": {
    "definitions": {
      "patterns": {
        "RESOURCE-BOTTLENECK": "Resource constraint causing degradation"
      }
    },
    "system": {
      "state": ["WARN"]
    },
    "domains": {
      "compute": {
        "components": {
          "server.node_1": {
            "metrics": {
              "CPU": {
                "values": [82],
                "context": "near threshold"
              }
            },
            "status": "WARN"
          }
        }
      },
      "database": {
        "components": {
          "database.primary": {
            "metrics": {
              "CONN": {
                "values": [1568],
                "context": "elevated"
              }
            },
            "status": "NRM"
          }
        }
      }
    },
    "patterns": {
      "active": ["RESOURCE-BOTTLENECK"],
      "relationships": [
        {
          "type": "causal",
          "chain": [
            {
              "component": "server.node_1",
              "effect": "cpu_pressure"
            },
            {
              "component": "database.primary",
              "effect": "latency"
            }
          ]
        }
      ]
    }
  }
}
```

### Tier 3 (Complex) and Tier 4 (Advanced)

See the full examples section for more complex implementations.

## Validation Rules

These rules should be enforced for OCTAVE JSON validity:

1. **Required Elements**:
   - The top-level object must contain either an `octave` object or direct schema elements
   - `definitions` object with at least `patterns` must be present
   - `system` or `system_state` must be present
   - At least one domain with components must be present

2. **Pattern References**:
   - All patterns referenced in `patterns.active` must be defined in `definitions.patterns`
   - All components referenced in relationships must exist in domains
   - All event codes referenced in relationships must exist in the events array

3. **Value Consistency**:
   - Status values should be consistent across the document
   - Units should be consistent for the same metric types
   - Timestamps should be valid ISO 8601 format
   - Custom status codes should be defined in `definitions.statuses`

4. **Array Constraints**:
   - `values` arrays should contain at least one element
   - `state` arrays should contain at least one element
   - Relationship chains should contain at least two elements (source and target)

5. **Type Consistency**:
   - For numerical metrics (like CPU utilization), use number type consistently
   - For boolean states (like activation flags), use boolean type consistently
   - For string values (like status codes), use string type consistently

6. **Schema Versioning**:
   - Include a `schema_version` in metadata to track the JSON Schema version
   - Follow semantic versioning (MAJOR.MINOR.PATCH) for schema changes

## Implementation Guidelines

When implementing OCTAVE in JSON format, follow these guidelines for best results:

### Schema Validation Integration

1. **JSON Schema Validation**:
   - Use standard JSON Schema validators to ensure document validity
   - Implement the full schema definition in your validation pipeline
   - Create custom validators for rules not expressible in JSON Schema (like cross-references)

2. **Progressive Enhancement**:
   - Start with Tier 1 implementation for basic functionality
   - Add relationships and events as your implementation matures
   - Implement advanced features like recommendations when needed

3. **Data Type Selection**:

   When choosing data types for metric values, follow these guidelines:

   - **Number Type**: Use for quantitative measurements (CPU percentage, response time, etc.)
     ```json
     "CPU": { "values": [45, 68, 94], "unit": "%" }
     ```

   - **String Type**: Use for qualitative states, identifiers, and textual values
     ```json
     "ENVIRONMENT": { "values": ["dev", "staging", "prod"] }
     ```

   - **Boolean Type**: Use for binary states and flags
     ```json
     "ACTIVATION": { "values": [false, true] }
     ```

4. **Mythological Reference Usage**:
   - Include mythological references in domain definitions for semantic compression
   - Maintain consistent mapping between technical domains and mythological domains
   - Use pattern names that align with mythological concepts when relevant

5. **Cross-Reference Validation**:
   - Implement custom validation to ensure all referenced components exist
   - Verify that all patterns referenced in `active` are defined in `definitions.patterns`
   - Ensure all event codes referenced in relationships exist in the events array

6. **API Integration**:
   - Design endpoints to accept both standard and compact formats
   - Include content negotiation for different JSON representations
   - Return proper validation errors with specific locations of issues

### Best Practices

1. **Format Selection**:
   - Use standard format for readability and extensibility
   - Use compact format for minimal payload size in resource-constrained environments
   - Be consistent with your chosen format across your implementation

2. **Unit Consistency**:
   - Use consistent units for the same metric types
   - Include unit specification for all numerical metrics
   - Follow standard unit abbreviations (%, ms, MB, etc.)

3. **Progressive State Representation**:
   - Order values chronologically in `values` arrays
   - Use consistent time intervals when collecting sequential values
   - Add context annotations to explain significant changes

4. **Dynamic Schema Generation**:
   - Consider generating schema programmatically for complex implementations
   - Add custom keywords for domain-specific validation requirements
   - Include schema references ($schema) in JSON documents for validator selection

5. **Performance Optimization**:
   - Use compact format for high-volume telemetry data
   - Consider partial document updates for frequently changing metrics
   - Implement compression for large OCTAVE JSON documents

## Examples

### Simple Status Report

```json
{
  "octave": {
    "metadata": {
      "timestamp": "2025-04-21T14:30:00Z",
      "source": "System Monitoring",
      "schema_version": "1.0"
    },
    "definitions": {
      "patterns": {
        "RESOURCE-ALERT": "Resource threshold breach"
      }
    },
    "system": {
      "state": ["WARN"],
      "timestamp": "2025-04-21T14:30:00Z"
    },
    "domains": {
      "compute": {
        "components": {
          "server.node_1": {
            "metrics": {
              "CPU": {
                "values": [82],
                "unit": "%",
                "context": "near threshold"
              }
            },
            "status": "WARN"
          }
        }
      }
    }
  }
}
```

### System Degradation with Relationship

```json
{
  "octave": {
    "version": "6.0.0",
    "metadata": {
      "timestamp": "2025-04-21T14:30:00Z",
      "source": "System Monitoring",
      "schema_version": "1.0"
    },
    "definitions": {
      "patterns": {
        "OLYMPIAN-CASCADE": "Multiple systems failing in sequence"
      }
    },
    "system": {
      "state": ["NRM", "WARN", "DEG"],
      "progression": true,
      "timestamp": "2025-04-21T14:30:00Z"
    },
    "domains": {
      "compute": {
        "mythological_reference": "Zeus's Realm",
        "components": {
          "server.node_1": {
            "alias": "N1",
            "metrics": {
              "CPU": {
                "values": [45, 68, 94],
                "unit": "%",
                "context": "exponential growth"
              }
            },
            "status": "DEG"
          }
        }
      },
      "database": {
        "mythological_reference": "Poseidon's Waters",
        "components": {
          "database.primary": {
            "alias": "DB1",
            "metrics": {
              "CONN": {
                "values": [837, 1024, 2047],
                "context": "saturating"
              }
            },
            "status": "WARN"
          }
        }
      }
    },
    "events": [
      {
        "code": "DB-IDX",
        "timestamp": "2025-04-21T07:45:00Z",
        "description": "Database index rebuild"
      }
    ],
    "patterns": {
      "active": ["OLYMPIAN-CASCADE"],
      "relationships": [
        {
          "type": "causal",
          "chain": [
            {
              "component": "DB-IDX",
              "effect": "schema_lock"
            },
            {
              "component": "DB1",
              "effect": "connection_saturation"
            },
            {
              "component": "N1",
              "effect": "cpu_spike"
            }
          ]
        }
      ]
    }
  }
}
```

For complete examples, see:
- [`examples/simple.json`](../examples/simple.json)
- [`examples/cloud-system-equivalent.json`](../examples/cloud-system-equivalent.json)

## JSON Schema Definition

Below is a formal JSON Schema definition that can be used for validation:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://example.com/octave-schema/v1.0.json",
  "title": "OCTAVE JSON Schema",
  "description": "JSON Schema for the OCTAVE semantic specification",
  "type": "object",
  "oneOf": [
    {
      "required": ["octave"],
      "properties": {
        "octave": {
          "$ref": "#/definitions/octaveRoot",
          "description": "Root container for OCTAVE document with standard format"
        }
      }
    },
    {
      "$ref": "#/definitions/octaveRoot",
      "description": "Root elements for OCTAVE document with compact format"
    }
  ],
  "definitions": {
    "octaveRoot": {
      "type": "object",
      "required": ["definitions", "domains"],
      "oneOf": [
        { "required": ["system"] },
        { "required": ["system_state"] }
      ],
      "properties": {
        "version": {
          "type": "string",
          "description": "OCTAVE version number"
        },
        "metadata": {
          "type": "object",
          "description": "Document metadata information",
          "properties": {
            "timestamp": {
              "type": "string",
              "format": "date-time",
              "description": "ISO 8601 timestamp when document was created"
            },
            "source": {
              "type": "string",
              "description": "System or component that generated the document"
            },
            "implementation": {
              "type": "string",
              "description": "Implementation format, e.g., 'JSON'"
            },
            "title": {
              "type": "string",
              "description": "Human-readable document title"
            },
            "license": {
              "type": "string",
              "description": "License information"
            },
            "schema_version": {
              "type": "string",
              "description": "Version of the JSON schema used for this document",
              "pattern": "^\\d+\\.\\d+(\\.\\d+)?$"
            }
          }
        },
        "definitions": {
          "type": "object",
          "description": "Pattern and status definitions",
          "required": ["patterns"],
          "properties": {
            "patterns": {
              "type": "object",
              "description": "Pattern definitions with descriptions",
              "additionalProperties": {
                "type": "string",
                "description": "Pattern description"
              }
            },
            "statuses": {
              "type": "object",
              "description": "Custom status code definitions",
              "additionalProperties": {
                "type": "string",
                "description": "Status description"
              }
            }
          }
        },
        "system": {
          "type": "object",
          "description": "System state information in standard format",
          "required": ["state"],
          "properties": {
            "state": {
              "type": "array",
              "description": "Current system state or state progression",
              "items": {
                "type": "string",
                "description": "State code"
              },
              "minItems": 1
            },
            "progression": {
              "type": "boolean",
              "description": "Whether state array represents progression over time"
            },
            "timestamp": {
              "type": "string",
              "format": "date-time",
              "description": "When the state was recorded"
            }
          }
        },
        "system_state": {
          "type": "object",
          "description": "System state information in compact format",
          "properties": {
            "progression": {
              "type": "array",
              "description": "State progression sequence",
              "items": {
                "type": "string",
                "description": "State code"
              }
            },
            "current": {
              "type": "string",
              "description": "Current system state"
            },
            "timestamp": {
              "type": "string",
              "format": "date-time",
              "description": "When the state was recorded"
            }
          }
        },
        "domains": {
          "description": "Functional domains containing components",
          "oneOf": [
            {
              "type": "object",
              "description": "Domains in standard object format",
              "additionalProperties": { "$ref": "#/definitions/domain" }
            },
            {
              "type": "array",
              "description": "Domains in compact array format",
              "items": { "$ref": "#/definitions/domainArray" }
            }
          ]
        },
        "events": {
          "type": "array",
          "description": "Significant system events",
          "items": {
            "type": "object",
            "required": ["code", "timestamp"],
            "properties": {
              "code": {
                "type": "string",
                "description": "Event identifier code"
              },
              "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "When the event occurred"
              },
              "description": {
                "type": "string",
                "description": "Human-readable event description"
              }
            }
          }
        },
        "patterns": {
          "type": "object",
          "description": "Active patterns and relationships",
          "properties": {
            "active": {
              "type": "array",
              "description": "Currently active patterns",
              "items": {
                "type": "string",
                "description": "Pattern identifier that must be defined in definitions.patterns"
              }
            },
            "relationships": {
              "type": "array",
              "description": "Relationships between components",
              "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                  "type": {
                    "type": "string",
                    "description": "Relationship type (causal, bidirectional, etc.)"
                  },
                  "chain": {
                    "type": "array",
                    "description": "Causal chain of components and effects",
                    "items": {
                      "type": "object",
                      "required": ["component"],
                      "properties": {
                        "component": {
                          "type": "string",
                          "description": "Component identifier or event code"
                        },
                        "effect": {
                          "type": "string",
                          "description": "Effect on or caused by the component"
                        }
                      }
                    },
                    "minItems": 2
                  },
                  "components": {
                    "type": "array",
                    "description": "Components in non-causal relationships",
                    "items": {
                      "type": "object",
                      "required": ["component"],
                      "properties": {
                        "component": {
                          "type": "string",
                          "description": "Component identifier"
                        },
                        "effect": {
                          "type": "string",
                          "description": "Effect related to the component"
                        }
                      }
                    },
                    "minItems": 2
                  },
                  "sequence": {
                    "type": "array",
                    "description": "Sequence of related components (compact format)",
                    "items": {
                      "type": "object",
                      "required": ["component"],
                      "properties": {
                        "component": {
                          "type": "string",
                          "description": "Component identifier"
                        },
                        "effect": {
                          "type": "string",
                          "description": "Effect related to the component"
                        }
                      }
                    },
                    "minItems": 2
                  }
                }
              }
            }
          }
        },
        "relationships": {
          "type": "array",
          "description": "Component relationships in compact format",
          "items": {
            "type": "object",
            "required": ["type"],
            "properties": {
              "type": {
                "type": "string",
                "description": "Relationship type"
              },
              "sequence": {
                "type": "array",
                "description": "Sequence of related components",
                "items": {
                  "type": "object",
                  "required": ["component"],
                  "properties": {
                    "component": {
                      "type": "string",
                      "description": "Component identifier"
                    },
                    "effect": {
                      "type": "string",
                      "description": "Effect related to the component"
                    }
                  }
                },
                "minItems": 2
              }
            }
          }
        },
        "recommendations": {
          "type": "array",
          "description": "Recommended actions",
          "items": {
            "type": "object",
            "required": ["action", "target"],
            "properties": {
              "action": {
                "type": "string",
                "description": "Recommended action to take"
              },
              "target": {
                "type": "string",
                "description": "Component or system to apply action to"
              },
              "priority": {
                "type": "string",
                "description": "Action priority (high, medium, low, etc.)"
              },
              "expected_impact": {
                "type": "string",
                "description": "Expected outcome of the action"
              }
            }
          }
        },
        "performance_analysis": {
          "type": "object",
          "description": "Performance metrics and analysis",
          "additionalProperties": {
            "type": "object",
            "description": "Performance metric",
            "properties": {
              "value": {
                "type": ["number", "string", "boolean"],
                "description": "Metric value"
              },
              "unit": {
                "type": "string",
                "description": "Unit of measurement"
              },
              "context": {
                "type": "string",
                "description": "Contextual information about the metric"
              }
            }
          }
        }
      }
    },
    "domain": {
      "type": "object",
      "description": "Domain in standard format",
      "required": ["components"],
      "properties": {
        "description": {
          "type": "string",
          "description": "Human-readable domain description"
        },
        "mythological_reference": {
          "type": "string",
          "description": "Mythological domain reference for semantic compression"
        },
        "components": {
          "type": "object",
          "description": "Components within the domain",
          "additionalProperties": { "$ref": "#/definitions/component" }
        }
      }
    },
    "domainArray": {
      "type": "object",
      "description": "Domain in compact array format",
      "required": ["name", "components"],
      "properties": {
        "name": {
          "type": "string",
          "description": "Domain name"
        },
        "category": {
          "type": "string",
          "description": "Domain category"
        },
        "components": {
          "type": "array",
          "description": "Components within the domain",
          "items": { "$ref": "#/definitions/componentArray" }
        }
      }
    },
    "component": {
      "type": "object",
      "description": "Component in standard format",
      "properties": {
        "alias": {
          "type": "string",
          "description": "Short alias for the component"
        },
        "metrics": {
          "type": "object",
          "description": "Component metrics",
          "additionalProperties": { "$ref": "#/definitions/metric" }
        },
        "status": {
          "type": "string",
          "description": "Component status code"
        }
      }
    },
    "componentArray": {
      "type": "object",
      "description": "Component in compact array format",
      "required": ["name"],
      "properties": {
        "name": {
          "type": "string",
          "description": "Component name"
        },
        "alias": {
          "type": "string",
          "description": "Short alias for the component"
        },
        "metrics": {
          "type": "object",
          "description": "Component metrics",
          "additionalProperties": { "$ref": "#/definitions/metric" }
        },
        "status": {
          "type": "string",
          "description": "Component status code"
        }
      }
    },
    "metric": {
      "type": "object",
      "description": "Metric with values and context",
      "required": ["values"],
      "properties": {
        "values": {
          "type": "array",
          "description": "Metric values, possibly showing progression over time",
          "items": {
            "type": ["number", "string", "boolean"],
            "description": "Metric value, type should be consistent within array"
          },
          "minItems": 1
        },
        "unit": {
          "type": "string",
          "description": "Unit of measurement"
        },
        "context": {
          "type": "string",
          "description": "Contextual information about the metric values"
        }
      }
    }
  }
}
```

This schema definition can be used with standard JSON Schema validators to ensure your OCTAVE JSON implementation conforms to the standard.

## Schema Versioning

This JSON Schema for OCTAVE follows semantic versioning (MAJOR.MINOR.PATCH):

| Schema Version | Description | Release Date |
|----------------|-------------|--------------|
| 1.0.0 | Initial release of OCTAVE JSON Schema | 2025-04-21 |

Future versions will maintain backward compatibility within the same major version. Breaking changes will be indicated by an increment in the major version number.

When implementing JSON Schema validation:

1. Include the schema version in your OCTAVE JSON documents:
   ```json
   "metadata": {
     "schema_version": "1.0.0"
   }
   ```

2. Reference the specific schema version in your validation:
   ```json
   {
     "$schema": "https://example.com/octave-schema/v1.0.json"
   }
   ```

3. Track schema versions in your implementation to ensure compatibility.

For guidance on implementing specific schema versions or handling migrations, refer to the versioned schema documentation.
