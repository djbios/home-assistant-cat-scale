# Cat scale integration for Home Assistant
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/djbios)
![CI](https://github.com/github/docs/actions/workflows/tests.yml/badge.svg)
Using simple weight sensors installed under the litterbox, this integration will provide you with the weight of your 
cat and the weight of their waste. 
This will allow you to monitor your cat's health and be alerted to any potential issues.

## Installation
Copy the `custom_components/cat_scale` folder to your Home Assistant `custom_components` folder.

## Configuration
This is the example configuration for the cat scale integration: 

```yaml
sensor:
  - platform: cat_scale
    name: "Cat weight"
    source_sensor: sensor.weight_sensor # The entity_id of the weight sensor
    cat_weight_threshold: 900 # The weight threshold, in grams, to determine if the cat is present
    min_presence_time: 3 # The minimum time, in seconds, the cat must be present to be considered present
    leave_timeout: 45 # The time, in seconds, the cat must be absent to be considered gone, or we will assume it's a new baseline (litter added or smth)
```

## Algorithm Overview

### Baseline Weight

The scale has a stable baseline when the litterbox is “empty” (no cat).
Over time, the sensor adjusts its baseline if the scale remains below the detection threshold (i.e., no cat presence).

### Cat Detection

We watch for the weight to exceed (baseline_weight + cat_weight_threshold).
If the weight stays above that threshold for at least min_presence_time seconds, we confirm the cat is present.
We record the peak weight during the cat’s stay.

### Cat Leaves

Once the weight drops back below the threshold, we finalize the cat’s weight as
cat_weight
=
peak_weight
−
baseline_weight
cat_weight=peak_weight−baseline_weight
We update the baseline to the new scale reading (assuming the cat has left).

### Waste Weight

We also track the baseline before the cat arrived vs. the new baseline after the cat leaves.
The difference is the “waste weight,” i.e., how much extra mass ended up in the litter box.

waste_weight=new_baseline−pre_cat_baseline

### Detection States

idle – No cat detected, baseline is stable (or being adjusted).
waiting_for_confirmation – The scale exceeded threshold, waiting to confirm presence.
cat_present – Cat has been confirmed present.


## Hardware
Basically, all you need is a weight sensor under the litterbox and a microcontroller to read the sensor and send the data to Home Assistant.
The simplest way to do this is to use an HX711 amplifier and a load cell/cells connected to an ESP8266/ESP32 microcontroller via ESPHome.
Here is an example of the ESPHome configuration:

```yaml
esphome:
  name: litterbox

esp8266:
  board: d1_mini

# Enable logging
logger:
  level: DEBUG

# Enable Home Assistant API
api:
  password: ""

ota:
  platform: esphome
  password: ""

wifi:
  ssid: "MyWIFI"
  password: "123qweasdzxc"

sensor:
  - platform: hx711
    name: "Cat Weight Sensor"
    dout_pin: D1
    clk_pin: D3
    gain: 128
    update_interval: 2s
    filters:
      - calibrate_linear:
          - 212999 -> 0
          - 269866 -> 2100
          - 413236 -> 7800
      
      - clamp:
          min_value: 0
          max_value: 100000
          ignore_out_of_range: true
```
Don't forget to adjust the calibration values for your sensor, details can be found in the [ESPHome documentation](https://esphome.io/components/sensor/hx711.html).


