# Cat scale integration for Home Assistant

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