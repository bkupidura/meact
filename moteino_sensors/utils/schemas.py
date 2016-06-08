SCHEMA_DEFINITIONS = {
  "notEmptyString": {
    "type": "string",
    "minLength": 1
  },
  "boardID": {
    "type": "string",
    "minLength": 1,
    "pattern": "^[a-zA-Z0-9]+$"
  },
  "action": {
    "type": "array",
    "minItems": 1,
    "uniqueItems": True,
    "items": {
      "type": "object",
      "properties": {
        "name": {"$ref": "#/definitions/notEmptyString"},
        "failback": {"$ref": "#/definitions/action"}
      },
      "required": ["name"]
    }
  },
  "actions": {
    "type": "array",
    "minItems": 1,
    "uniqueItems": True,
    "items": {
      "type": "object",
      "properties": {
        "action_interval": {
          "minimum": 0,
          "type": "integer",
          "default": 0
        },
        "fail_count": {
          "minimum": 0,
          "type": "integer",
          "default": 0
        },
        "fail_interval": {
          "minimum": 0,
          "type": "integer",
          "default": 600
        },
        "message_template": {
          "type": "string",
          "minLength": 1,
          "default": "{sensor_type} on board {board_desc} ({board_id}) reports value {sensor_data}"
        },
        "threshold": {
          "type": "string",
          "minLength": 1,
          "default": "lambda: True"
        },
        "board_ids": {
          "type": "array",
          "uniqueItems": True,
          "default": [],
          "items": {"$ref": "#/definitions/boardID"}
        },
        "check_status": {
          "type": "array",
          "uniqueItems": True,
          "default": [],
          "items": {
            "type": "object",
            "properties": {
              "name": {"$ref": "#/definitions/notEmptyString"},
              "threshold": {"$ref": "#/definitions/notEmptyString"}
            },
            "required": ["name", "threshold"]
          }
        },
        "check_metric": {
          "type": "array",
          "uniqueItems": True,
          "default": [],
          "items": {
            "type": "object",
            "properties": {
              "sensor_type": {"$ref": "#/definitions/notEmptyString"},
              "threshold": {"$ref": "#/definitions/notEmptyString"},
              "board_ids": {
                "type": "array",
                "uniqueItems": True,
                "default": [],
                "items": {"$ref": "#/definitions/boardID"}
              },
              "value_count": {
                "minimum": 0,
                "type": "integer",
                "default": 1
              }
            },
            "required": ["sensor_type", "threshold"]
          }
        },
        "action_config": {
          "type": "object",
          "default": {},
          "additionalProperties": {"type": "object"}
        },
        "action": {"$ref": "#/definitions/action"}
      },
      "required": ["action"]
    }
  }
}

SCHEMA_SENSOR_DATA = {
  "definitions": SCHEMA_DEFINITIONS,
  "type": "object",
  "properties": {
    "board_id": {"$ref": "#/definitions/boardID"},
    "sensor_type": {"$ref": "#/definitions/notEmptyString"},
    "sensor_data": {"$ref": "#/definitions/notEmptyString"},
  },
  "required": [
    "board_id",
    "sensor_type",
    "sensor_data"
  ]
}

SCHEMA_SENSOR_CONFIG = {
  "definitions": SCHEMA_DEFINITIONS,
  "type": "object",
  "properties": {
    "priority": {
      "minimum": 0,
      "type": "integer",
      "default": 500
    },
    "value_count": {
      "minimum": 0,
      "type": "integer",
      "default": 0
    },
    "actions": {"$ref": "#/definitions/actions"}
  },
  "required": ["actions"]
}
