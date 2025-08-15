
**⚠️ Breaking Change in v2.0.0**
>
> This release introduces a new configuration system using the Home Assistant UI.  
> **Manual YAML configuration is no longer supported.**
>
> **To migrate:**
> 1. Remove any `cat_scale` configuration from your `configuration.yaml`.
> 2. Delete the old Cat Scale integration from Home Assistant if it is present.
> 3. Go to **Settings → Devices & Services → Add Integration → Cat weight tracker** and set up your sensor using the UI.
>
> **Why this change?**
> - The integration now supports full UI configuration, unique IDs, device management, and improved Home Assistant compatibility.
> - This makes setup easier and enables new features like renaming, device grouping, and long-term statistics.
>
> If you have any issues, please check the [issue tracker](https://github.com/djbios/home-assistant-cat-scale/issues) or open a new issue for help.
# Cat scale integration for Home Assistant

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/djbios)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=djbios&repository=home-assistant-cat-scale&category=integration)

![CI](https://github.com/djbios/home-assistant-cat-scale/actions/workflows/tests.yml/badge.svg)
[![codecov](https://codecov.io/gh/djbios/home-assistant-cat-scale/graph/badge.svg?token=FMNZKAWIS8)](https://codecov.io/gh/djbios/home-assistant-cat-scale)

<img src="https://pic.djbios.org/r3qe8x.png" alt="drawing" width="400"/>


Using simple weight sensors installed under the litterbox, this integration will provide you with the weight of your 
cat and the weight of their waste. 
This will allow you to monitor your cat's health and be alerted to any potential issues.

## Installation
### Manual
Copy the `custom_components/cat_scale` folder to your Home Assistant `custom_components` folder.

### HACS
HACS > Integrations > 3 dots > Custom repositories > URL: `djbios/home-assistant-cat-scale`, Category: Integration > Add > wait > Search "cat scale" > Install
![HACS](https://pic.djbios.org/yjf622.gif)

### Dashboard example
![qwe](https://pic.djbios.org/ijo4jd.png)

## Configuration
After installing the integration through HACS, the sensor can be configured through home assistant UI.
Settings -> Devices & Services -> Add integration -> Cat weight tracker

You will be asked for:
  - **Source sensor**: the weight sensor to be used as source for this integration. Make sure your sensor is of device_type 'weight'
  - **Cat weight threshold**: The weight threshold, in grams, to determine if the cat is present
  - **Minimum presence time**: The minimum time, in seconds, the cat must be present to be considered present
  - **Leave timeout**: The time, in seconds, the cat must be absent to be considered gone, or we will assume it's a new baseline (litter added or smth)
  - **After-cat standard deviation**: Deviation value used to determine whether a cat left / is present. Default value is usually good enough

Configuration recomendations:
- `cat_weight_threshold` should be set to the average weight of your cat deducting 20-30%.
- To set `min_presence_time` use your weight sensor historical data and set it to the average time your cat spends in the litterbox deducting 10-20%.
- `leave_timeout` depends on your cat's behavior, if your cat is often in and out of the litterbox, you should set it to a higher value.

## Algorithm Overview

### Baseline Weight

The scale has a stable baseline when the litterbox is “empty” (no cat).
Over time, the sensor adjusts its baseline if the scale remains below the detection threshold (i.e., no cat presence).

### Cat Detection

We watch for the weight to exceed `baseline_weight + cat_weight_threshold`.
If the weight stays above that threshold for at least `min_presence_time` seconds, we confirm the cat is present.
We record the peak weight during the cat’s stay.

### Cat Leaves

Once the weight drops back below the threshold, we finalize the cat’s weight as `cat_weight=peak_weight−baseline_weight`
we update the baseline to the new scale reading (assuming the cat has left).

### Waste Weight

We also track the baseline before the cat arrived vs. the new baseline after the cat leaves.
The difference is the “waste weight,” i.e., how much extra mass ended up in the litter box `waste_weight=new_baseline−pre_cat_baseline`

### Detection States

- `idle` – No cat detected, baseline is stable (or being adjusted).
- `waiting_for_confirmation` – The scale exceeded threshold, waiting to confirm presence.
- `cat_present` – Cat has been confirmed present.


## Hardware
Basically, all you need is a weight sensor under the litterbox and a microcontroller to read the sensor and send the data to Home Assistant.
The simplest way to do this is to use an HX711 amplifier and a load cell/cells connected to an ESP8266/ESP32 microcontroller via ESPHome.
Here is an example of the ESPHome configuration:

```yaml
esphome:
  name: litterbox

esp8266:
  board: d1_mini

# Enable Home Assistant API
api:
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
    unit_of_measurement: g
    device_class: weight
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


