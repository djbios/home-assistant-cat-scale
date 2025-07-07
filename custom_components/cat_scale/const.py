"""Constants for the Cat Scale integration."""

DOMAIN = "cat_scale"

CONF_SOURCE_SENSOR = "source_sensor"
CONF_CAT_WEIGHT_THRESHOLD = "cat_weight_threshold"
CONF_MIN_PRESENCE_TIME = "min_presence_time"
CONF_LEAVE_TIMEOUT = "leave_timeout"
CONF_AFTER_CAT_STANDARD_DEVIATION = "after_cat_standard_deviation"

DEFAULT_CAT_WEIGHT_THRESHOLD = 1000
DEFAULT_MIN_PRESENCE_TIME = 4
DEFAULT_LEAVE_TIMEOUT = 120
DEFAULT_AFTER_CAT_STANDARD_DEVIATION = 50  # or your preferred default
