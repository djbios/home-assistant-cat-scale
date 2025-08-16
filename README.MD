# Cat scale integration for Home Assistant

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=djbios&repository=home-assistant-cat-scale&category=integration)
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/djbios)

![CI](https://github.com/djbios/home-assistant-cat-scale/actions/workflows/tests.yml/badge.svg)
[![codecov](https://codecov.io/gh/djbios/home-assistant-cat-scale/graph/badge.svg?token=FMNZKAWIS8)](https://codecov.io/gh/djbios/home-assistant-cat-scale)


<img src="https://pic.djbios.org/r3qe8x.png" alt="drawing" width="400"/>


Using simple weight sensors installed under the litterbox, this integration will provide you with the weight of your 
cat and the weight of their waste. 
This will allow you to monitor your cat's health and be alerted to any potential issues.

## Installation

### HACS (Recommended)
This integration is available in the [default HACS repository](https://hacs.xyz/).  
To install:

1. Go to **Settings → Devices & Services → Add Integration → Cat weight tracker** in Home Assistant, or open HACS from the sidebar.
2. In HACS, search for **Cat scale** under Integrations.
3. Click **Install**.
4. Restart Home Assistant if prompted.

You can also use the button below to open the repository directly in HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=djbios&repository=home-assistant-cat-scale&category=integration)

### Manual
If you prefer manual installation:

1. Copy the `custom_components/cat_scale` folder to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

> **Note:** Manual installation is not recommended unless you have a specific need.

### Dashboard example
![qwe](https://pic.djbios.org/ijo4jd.png)

## Configuration
After installing the integration through HACS, the sensor can be configured through home assistant UI.
Settings -> Devices & Services -> Add integration -> Cat weight tracker

You will be asked for:
  - **Source sensor**: the weight sensor to be used as source for this integration. Make sure your sensor is of device_type 'weight'
  - **Cat weight threshold**: The weight threshold, in grams, to determine if the cat is present
  - **Minimum presence time**: The minimum time, in seconds, the cat must be present to be considered present
  - **Leave timeout**: The time, in seconds, the cat must be absent to be considered gone, or we will assume it's a new baseline (litter added or something)
  - **After-cat standard deviation**: Deviation value used to determine whether a cat left / is present. Default value is usually good enough

Configuration recommendations:
- `cat_weight_threshold` should be set to the average weight of your cat subtracting 20-30%.
- To set `min_presence_time` use your weight sensor historical data and set it to the average time your cat spends in the litterbox subtracting 10-20%.
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

You will need:
- **Weight sensor(s):** e.g., [M5stack scales kit](https://docs.m5stack.com/en/app/scales_kit)  
  *Note: This kit may not be accurate for lightweight cats. For small cats, consider a higher-sensitivity load cell with less capacity (these are 200kg total).*
- **Microcontroller:** e.g., [M5stack esp32-c6](https://docs.m5stack.com/en/core/M5NanoC6) or any ESP8266/ESP32 compatible with ESPHome
- **Stable power supply**

The simplest way is to use an HX711 amplifier and a load cell connected to an ESP8266/ESP32 running ESPHome.

For a more complete esphome configuration, see our complete [example configuration](./esphome/example_full_m5stack_scaleset.yaml).

> ⚠️ **Calibration is critical:** Be sure to calibrate your sensor for accurate results. See the [ESPHome documentation](https://esphome.io/components/sensor/hx711.html) for details. This can be done with the `calibrate_linear` values.

Feel free to open an [issue](https://github.com/djbios/home-assistant-cat-scale/issues) or PR if you have recommendations for the ESPHome configuration!

```yaml
esphome:
  name: catscale
  friendly_name: Cat-scale

esp32:
  board: esp32-c6-devkitm-1
  variant: esp32c6
  framework:
    type: esp-idf

# Enable Home Assistant API
api:
  encryption:
    key: !secret encryption_key

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

sensor:
  - platform: hx711
    name: "Cat Weight Sensor"
    dout_pin: GPIO32
    clk_pin: GPIO26

    gain: 128
    update_interval: 1s
    unit_of_measurement: g
    device_class: weight
    accuracy_decimals: 0
    filters:
      - calibrate_linear:
          - 148937 -> 0 # Add own calibration here!
          - 2055181 -> 73900 # Add own calibration here!
      - clamp:
          min_value: -10000
          max_value: 200000
          ignore_out_of_range: true

```

## Migration notes

**Migrating from a version before 2.0.0?**  
Manual YAML configuration is no longer supported.  
Please remove any `cat_scale` entries from your `configuration.yaml` and re-add the integration using the Home Assistant UI.

For more help, see the [issue tracker](https://github.com/djbios/home-assistant-cat-scale/issues).

