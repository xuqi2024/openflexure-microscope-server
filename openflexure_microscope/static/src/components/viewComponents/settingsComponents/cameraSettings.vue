<template>
  <div v-if="settings" id="cameraSettings">
    <div>
      <h3>Manual camera settings</h3>
      <form @submit.prevent="applyConfigRequest">
        <div v-if="settings.picamera">
          <!--PiCamera settings block-->
          <div v-if="settings.picamera.shutter_speed !== undefined">
            <label class="uk-form-label" for="form-stacked-text"
              >Exposure time</label
            >
            <div class="uk-form-controls">
              <input
                v-model="settings.picamera.shutter_speed"
                class="uk-input uk-form-small"
                type="number"
              />
            </div>
          </div>

          <div v-if="settings.picamera.analog_gain !== undefined">
            <label class="uk-form-label" for="form-stacked-text"
              >Analogue gain</label
            >
            <div class="uk-form-controls">
              <input
                v-model="settings.picamera.analog_gain"
                class="uk-input uk-form-small"
                type="number"
                step="0.000001"
              />
            </div>
          </div>

          <div v-if="settings.picamera.digital_gain !== undefined">
            <label class="uk-form-label" for="form-stacked-text"
              >Digital gain</label
            >
            <div class="uk-form-controls">
              <input
                v-model="settings.picamera.digital_gain"
                class="uk-input uk-form-small"
                type="number"
                step="0.000001"
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          class="uk-button uk-button-primary uk-margin-small uk-width-1-1"
        >
          Apply Settings
        </button>
      </form>
    </div>

    <!--Show auto calibrate if default plugin is enabled-->
    <h3>Automatic calibration</h3>
    <cameraCalibrationSettings></cameraCalibrationSettings>
  </div>
</template>

<script>
import axios from "axios";
import cameraCalibrationSettings from "./cameraCalibrationSettings.vue";

// Export main app
export default {
  name: "CameraSettings",

  components: {
    cameraCalibrationSettings
  },

  data: function() {
    return {
      settings: {}
    };
  },

  computed: {
    settingsUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/instrument/settings`;
    }
  },

  mounted() {
    this.updateSettings();
  },

  methods: {
    updateSettings: function() {
      axios
        .get(this.settingsUri)
        .then(response => {
          this.settings = response.data.camera;
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    applyConfigRequest: function() {
      console.log("Applying config to the microscope");
      var payload = {
        camera: {
          picamera: {
            shutter_speed: this.settings.picamera.shutter_speed,
            analog_gain: this.settings.picamera.analog_gain,
            digital_gain: this.settings.picamera.digital_gain
          }
        }
      };

      // Send request
      axios
        .put(this.settingsUri, payload)
        .then(() => {
          return new Promise(r => setTimeout(r, 500));
        }) // why is there no built-in for this??!
        .then(() => {
          // Update local settings
          this.updateSettings();
          this.modalNotify("Camera settings applied.");
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    }
  }
};
</script>

<style lang="less"></style>
