<template>
  <div id="cameraSettings">
    <div class="uk-grid uk-grid-divider uk-child-width-expand" uk-grid>
      <div class="uk-width-large">
        <h3>Automatic calibration</h3>
        <cameraCalibrationSettings :camera-uri="cameraUri" />

        <h3>Manual camera settings</h3>
        <form @submit.prevent="applySettingsRequest">
          <div class="uk-margin-small-bottom">
            <ul uk-accordion="multiple: true">
              <li class="uk-open">
                <a class="uk-accordion-title" href="#">Pi Camera Settings</a>
                <div class="uk-accordion-content">
                  <PropertyControl
                    label="Exposure time (0-33251)"
                    property-name="exposure_time"
                    thing-name="camera"
                    :read-back-delay="1000"
                  />
                  <PropertyControl
                    label="Analogue gain"
                    property-name="analogue_gain"
                    thing-name="camera"
                    :read-back-delay="1000"
                  />
                  <PropertyControl
                    label="Colour gains"
                    property-name="colour_gains"
                    thing-name="camera"
                    :read-back-delay="1000"
                  />
                </div>
              </li>
              <li class="uk-open">
                <a class="uk-accordion-title" href="#">Image Quality</a>
                <div class="uk-accordion-content">
                  <PropertyControl
                    label="MJPEG stream bit rate"
                    property-name="mjpeg_bitrate"
                    thing-name="camera"
                    :read-back-delay="100"
                  />
                  <PropertyControl
                    label="MJPEG stream resolution"
                    property-name="stream_resolution"
                    thing-name="camera"
                    :read-back-delay="100"
                  />
                </div>
              </li>
              <!--
              <li>
                <a class="uk-accordion-title" href="#">Advanced</a>
                <div class="uk-accordion-content">

                  <div
                    v-if="picamera.framerate !== undefined"
                    class="uk-margin-top"
                  >
                    <label class="uk-form-label" for="form-stacked-text"
                      >Camera framerate</label
                    >
                    <select
                      v-model="picamera.framerate"
                      class="uk-select uk-form-small"
                    >
                      <option
                        v-for="option in framerateOptions"
                        :key="option.value"
                        :value="option.value"
                      >
                        {{ option.text }}
                      </option>
                    </select>
                    <p class="uk-margin-remove">
                      This option sets the framerate of the Pi Camera video
                      encoder. The actual stream framerate is determined by
                      network speed, and is limited by the encoder framerate.<br />
                      <b>Lowering framerate may impact fast-autofocus accuracy.</b>
                    </p>
                  </div>
                </div>
              </li>-->
            </ul>
          </div>
        </form>
      </div>

      <div id="mini-stream">
        <miniStreamDisplay />
      </div>
    </div>
  </div>
</template>

<script>
import cameraCalibrationSettings from "./cameraSettingsComponents/cameraCalibrationSettings.vue";
import miniStreamDisplay from "../../genericComponents/miniStreamDisplay.vue";
import PropertyControl from "../../labThingsComponents/propertyControl.vue";

// Export main app
export default {
  name: "CameraSettings",

  components: {
    cameraCalibrationSettings,
    miniStreamDisplay,
    PropertyControl
  },

  data: function() {
    return {
      picamera: {
        shutter_speed: undefined,
        analog_gain: undefined,
        digital_gain: undefined,
        framerate: undefined,
        awb_gains: undefined
      },
      mjpeg_bitrate: undefined,
      stream_resolution: undefined,
      jpeg_quality: undefined,
      bitrateOptions: [
        { text: "Maximum (unlimited)", value: -1 },
        { text: "High (25Mbps)", value: 25000000 },
        { text: "Normal (17Mbps)", value: 17000000 },
        { text: "Low (5Mbps)", value: 5000000 },
        { text: "Very low (2.5Mbps)", value: 2500000 }
      ],
      resolutionOptions: [
        { text: "Higher (832, 624)", value: [832, 624] },
        { text: "Normal (640, 480)", value: [640, 480] }
      ],
      framerateOptions: [
        { text: "Normal (30fps)", value: 30 },
        { text: "Low (15fps)", value: 15 },
        { text: "Very low (10fps)", value: 10 }
      ]
    };
  },

  computed: {
    cameraUri: function() {
      return `${this.$store.getters.baseUri}/camera/`;
    }
  }
};
</script>

<style lang="less">
#mini-stream {
  min-width: 300px;
  max-width: 600px;
  text-align: center;
  margin-left: auto;
  margin-right: auto;
  margin-top: 50px;
}
</style>
