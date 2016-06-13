SCHEMA_DEFINITIONS = {
  "notEmptyString": {
    "type": "string",
    "minLength": 1
  },
  "positiveInteger": {
    "minimum": 0,
    "type": "integer"
  },
  "boardID": {
    "type": "string",
    "minLength": 1,
    "pattern": "^[a-zA-Z0-9\-]+$"
  },
  "boardIDs": {
    "type": "array",
    "uniqueItems": True,
    "items": {"$ref": "#/definitions/boardID"}
  },
  "valueCount": {
    "oneOf": [
      {
        "type": "object",
        "properties": {
          "type": {"$ref": "#/definitions/notEmptyString"},
          "count": {"$ref": "#/definitions/positiveInteger"}
        },
        "required": ["type", "count"]
      },
      {
        "type": "object",
        "properties": {},
        "additionalProperties": False
      }
    ]
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
        "action_interval": {"$ref": "#/definitions/positiveInteger"},
        "fail_count": {"$ref": "#/definitions/positiveInteger"},
        "fail_interval": {"$ref": "#/definitions/positiveInteger"},
        "message_template": {"$ref": "#/definitions/notEmptyString"},
        "threshold": {"$ref": "#/definitions/notEmptyString"},
        "value_count": {"$ref": "#/definitions/valueCount"},
        "board_ids": {"$ref": "#/definitions/boardIDs"},
        "transform": {"type": "string"},
        "check_status": {
          "type": "array",
          "uniqueItems": True,
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
          "items": {
            "type": "object",
            "properties": {
              "sensor_type": {"$ref": "#/definitions/notEmptyString"},
              "threshold": {"$ref": "#/definitions/notEmptyString"},
              "board_ids": {"$ref": "#/definitions/boardIDs"},
              "value_count": {"$ref": "#/definitions/valueCount"}
            },
            "required": ["sensor_type", "threshold", "board_ids", "value_count"]
          }
        },
        "action_config": {
          "type": "object",
          "additionalProperties": {"type": "object"}
        },
        "action": {"$ref": "#/definitions/action"}
      },
      "required": ["action", "action_interval", "fail_count", "fail_interval",
          "message_template", "threshold", "transform", "value_count",
          "board_ids", "check_status", "check_metric", "action_config"]
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
    "priority": {"$ref": "#/definitions/positiveInteger"},
    "actions": {"$ref": "#/definitions/actions"}
  },
  "required": ["priority", "actions"]
}

SCHEMA_FEED_CONFIG = {
  "definitions": SCHEMA_DEFINITIONS,
  "type": "object",
  "properties": {
    "name": {"$ref": "#/definitions/notEmptyString"},
    "expression": {"$ref": "#/definitions/notEmptyString"},
    "mqtt_topic": {"$ref": "#/definitions/notEmptyString"},
    "feed_interval": {"$ref": "#/definitions/positiveInteger"},
    "fail_interval": {"$ref": "#/definitions/positiveInteger"},
    "params": {"type": "object"}
  },
  "required": [
      "name",
      "expression",
      "mqtt_topic",
      "feed_interval",
      "fail_interval",
      "params"
  ]
}
