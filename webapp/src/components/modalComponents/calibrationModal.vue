<template>
  <div id="modal-example" ref="calibrationModalEl" uk-modal="bg-close: false;">
    <div v-if="ready" class="uk-modal-dialog uk-modal-body">
      <h2 class="uk-modal-title">Microscope Calibration</h2>
      <div v-show="stepValue == 0">
        <p>
          <b
            >Some important microscope calibration data is currently missing.</b
          >
        </p>
        <p>
          Your microscope will still function, however some functionality will
          be limited, and image quality will likely suffer.
        </p>
        <p>
          <b>Click Next to begin microscope calibration.</b>
        </p>
      </div>
      
      <!--Panel checks if the user has built the microscope or bought it from a supplier. 
      If bought from a supplier, skips assembly setup questions.-->
      <div v-show="stepValue == 1">
        <p>
          <b
            >Did you build this microscope yourself?</b
          >
        </p>
        <div class = "centre">
          <button
          class="uk-button uk-button-default"
          type="button"
          @click="complete_config()">
              Yes
          </button>
          <button
          class="uk-button uk-button-default"
          type="button"
          @click="skip_config()">
              No
          </button>
        </div>
      </div>
      
      <!--Section for gathering configuration information from user-->
      <div v-show="stepValue == 2">
        <h3>Assembly Configuration</h3>
        <p>
          <b
            >Please provide the following information to improve calibration analysis</b
          >
        </p>
        
        <!--Gear-->
        <div class="parent">
          <div class="child">
            <p>Gear Ratio</p>
          </div>
          <div class="child">
            <select name="Gear Ratio" id="gear">
              <option value="1:2(default)">1:2(default)</option>
              <option value="1:1/2">1:1/2</option>
              <option value="2:1">2:1</option>
              <option value="1:1">1:1</option>
              <option value="other">other</option>
            </select>
          </div>
        </div>

        <!--Stage-->
        <div class="parent">
          <div class="child">
            <p>Stage Type</p>
          </div>
          <div class="child">
            <select name="Stage Type" id="stage">
              <option value="default">default</option>
              <option value="Extended">Extended</option>
              <option value="other">other</option>
            </select>
          </div>
        </div>

        <!--Camera-->
        <div class="parent">
          <div class="child">
            <p>Camera Type</p>
          </div>
          <div class="child">
            <select name="Camera Type" id="camera">
              <option value="Raspberry Pi Camera V2 (default)">Raspberry Pi Camera V2 (default)</option>
              <option value="other">other</option>
            </select>
          </div>
        </div>

        <!--Stage-->
        <div class="parent">
          <div class="child">
            <p>Printer Used</p>
          </div>
          <div class="child">
            <select name="Printer Used" id="printer">
              <option value="Prusa">Prusa</option>
              <option value="Bamboo">Bamboo</option>
              <option value="other">other</option>
            </select>
          </div>
        </div>

        <!--Filament-->
        <div class="parent">
          <div class="child">
            <p>Filament Used:</p>
          </div>
          <div class="child">
            <select name="FilamentUsed" id="filament">
              <option value="PLA">PLA (Recommended)</option>
              <option value="PETG">PETG</option>
              <option value="other">other</option>
            </select>
          </div>
        </div>

        <!--Magnification-->
        <div class="parent">
          <div class="child">
            <p>Magnification</p>
          </div>
          <div class="child">
            <select name="Magnification" id="magnification">
              <option value="10x">10x</option>
              <option value="20x">20x</option>
              <option value="40x">40x</option>
              <option value="60x">60x</option>
              <option value="100x">100x</option>
              <option value="other">other</option>
            </select>
          </div>
        </div>

        <!--Temperature-->
        <div class="parent">
          <div class="child">
            <p>Temperature</p>
          </div>
          <div class="child">
            <select name="Temperature" id="temperature">
              <option value="Sub Zero">Sub Zero</option>
              <option value="0-10">0-10</option>
              <option value="10-20">10-20</option>
              <option value="20-30">20-30</option>
              <option value="30-40">30-40</option>
              <option value="Greater than 40">Greater than 40</option>
            </select>
          </div>
        </div>

        <p>
          <b>Click Next to continue microscope calibration.</b>
        </p>

        <button
        class="uk-button uk-button-default"
        @click="downloadTextFile()">
            Submit
        </button>
      </div>

      <div v-show="stepValue == 3">
        <h3>Lens-shading</h3>
        <div v-if="isLSTCalibrated">
          <p>
            <b
              >Your lens-shading table has already been calibrated. Click Next
              to move on.</b
            >
          </p>
        </div>
        <div v-else>
          <p>
            <b
              >Follow the important steps below before starting lens-shading
              calibration!</b
            >
          </p>
          <ul class="uk-list uk-list-bullet">
            <li>Remove any samples from your microscope</li>
            <li>Ensure your illumination is on and properly fixed in place</li>
          </ul>

          <miniStreamDisplay
            v-if="stepValue == 3"
            class="mini-preview"
          ></miniStreamDisplay>

          <p>Once you're ready, click auto-calibrate.</p>

          <cameraCalibrationSettings
            :show-extra-settings="false"
            :camera-uri="cameraUri"
          ></cameraCalibrationSettings>
        </div>
      </div>

      <div v-show="stepValue == 4">
        <h3>Camera-stage mapping</h3>
        <div v-if="isCSMCalibrated">
          <p>
            <b
              >Your camera-stage mapping has already been calibrated. Click Next
              to move on.</b
            >
          </p>
        </div>
        <div v-else-if="!canCSMCalibrated">
          <p>
            <b
              >No stage connected. Please skip this step, or connect a valid
              stage, then reboot your microscope.</b
            >
          </p>
        </div>
        <div v-else>
          <p>
            <b
              >Follow the important steps below before starting camera-stage
              mapping calibration!</b
            >
          </p>
          <ul class="uk-list uk-list-bullet">
            <li>Insert a clearly visible sample to the microscope</li>
            <li>
              Ensure the sample is reasonably well centered on the microscope
              camera
            </li>
          </ul>

          <miniStreamDisplay
            v-if="stepValue == 4"
            class="mini-preview"
          ></miniStreamDisplay>

          <p>Once you're ready, click auto-calibrate.</p>

          <CSMCalibrationSettings
            :show-extra-settings="false"
          ></CSMCalibrationSettings>
        </div>
      </div>

      <div v-show="stepValue == 5">
        <h3>Range of Motion</h3>
          <p>
            <b
              >Follow the important steps below before starting range of motion 
              calibration!</b
            >
          </p>
          <ul class="uk-list uk-list-bullet">
            <li>Insert a clearly visible sample to the microscope</li>
            <li>
              Ensure the sample is reasonably well centered on the microscope
              camera
            </li>
            <li>Ensure the sample is densely featured.</li>
            <li>Ensure the sample is large enough to fully test the range of motion.
              <ul class="uk-list uk-list-bullet">
                <li>If you have printed a standard stage, the sample needs to be at least 12mm in diameter.</li>
                <li>Otherwise, the sample needs to have a diameter of the range of motion you specified.</li>
              </ul>
            </li>
          </ul>

          <miniStreamDisplay
            v-if="stepValue == 5"
            class="mini-preview"
          ></miniStreamDisplay>

          <p>Once you're ready, click auto-calibrate.</p>

          <ROMsettings
            :show-extra-settings="false"
          ></ROMsettings>
        </div>

      <div v-show="stepValue == 6">
        <p>
          <b>Calibration complete</b>
        </p>
        <p>
          Click Finish to return to your microscope, or Restart to re-run the
          calibration routine
        </p>
      </div>

      <p class="uk-text-right">
        <button
          v-show="stepValue == 0"
          class="uk-button uk-button-default uk-modal-close"
          type="button"
        >
          Cancel
        </button>
        <button
          v-show="stepValue == 6"
          class="uk-button uk-button-default"
          type="button"
          @click="stepValue = 0"
        >
          Restart
        </button>
        <button
          v-show="stepValue < 6 && stepValue != 1"
          class="uk-button uk-button-primary uk-margin-left"
          type="button"
          @click="increment()"
        >
          Next
        </button>
        <button
          v-show="stepValue == 6"
          class="uk-button uk-button-primary uk-margin-left"
          type="button"
          @click="hide()"
        >
          Finish
        </button>
      </p>
    </div>
  </div>  
</template>

<script>
import cameraCalibrationSettings from "../tabContentComponents/settingsComponents/cameraSettingsComponents/cameraCalibrationSettings.vue";
import CSMCalibrationSettings from "../tabContentComponents/settingsComponents/CSMSettingsComponents/CSMCalibrationSettings.vue";
import miniStreamDisplay from "../genericComponents/miniStreamDisplay.vue";
import ROMsettings from "../tabContentComponents/stageComponents/paneStage.vue"

export default {
  name: "CalibrationModal",

  components: {
    cameraCalibrationSettings,
    CSMCalibrationSettings,
    miniStreamDisplay,
    ROMsettings
  },

  data: function() {
    return {
      ready: false,
      stepValue: 0,
      isCSMCalibrated: undefined,
      isLSTCalibrated: undefined
    };
  },

  computed: {
    canCSMCalibrated: function() {
      // Assert CSM extension is enabled
      return this.thingAvailable("camera_stage_mapping");
    },
    canLSTCalibrated: function() {
      // Assert LST extension is enabled
      return (
        "calibrate_lens_shading" in this.thingDescription("camera").actions
      );
    },
    isUseful: function() {
      var CSMUseful = this.canCSMCalibrated && !this.isCSMCalibrated;
      var LSTUseful = this.canLSTCalibrated && !this.isLSTCalibrated;
      return CSMUseful || LSTUseful;
    },
    cameraUri: function() {
      return `${this.$store.getters.baseUri}/camera/`;
    }
  },

  mounted() {
    this.$refs["calibrationModalEl"].addEventListener("hidden", this.onHide);
  },

  methods: {
    show: async function() {
      // Check if the camera and stage are calibrated, if they can be
      if (this.canCSMCalibrated) {
        let csm = await this.readThingProperty(
          "camera_stage_mapping",
          "image_to_stage_displacement_matrix",
          true
        );
        this.isCSMCalibrated = Boolean(csm);
      }
      if (this.canLSTCalibrated) {
        this.isLSTCalibrated = await this.readThingProperty(
          "camera",
          "lens_shading_is_static"
        );
      }
      // Check if this calibration wizard can actually do anything useful
      if (this.isUseful) {
        this.ready = true;
        this.stepValue = 0;
        // Show the modal
        var el = this.$refs["calibrationModalEl"];
        this.showModalElement(el); // Calls the mixin
      } else {
        // If not useful, we just return the onClose event immediately
        this.onHide();
      }
    },
    // Forces modal to show on button press
    force_show: function() {
      this.ready = true;
      this.stepValue = 0;
        // Show the modal
        var el = this.$refs["calibrationModalEl"];
        this.showModalElement(el); // Calls the mixin
    },

    hide: function() {
      // Show the modal
      var el = this.$refs["calibrationModalEl"];
      this.hideModalElement(el); // Calls the mixin
      this.ready = false;
    },

    onHide: function() {
      this.$emit("onClose");
    },

    decrement: function() {
      if (this.stepValue > 0) {
        this.stepValue = this.stepValue - 1;
      }
    },

    increment: function() {
      // Upper bound on section number
      if (this.stepValue < 6) {
        this.stepValue = this.stepValue + 1;
        return true;
      }
    },
    downloadTextFile: function() {
        const fields = [
            document.getElementById("gear").value,
            document.getElementById("stage").value,
            document.getElementById("camera").value,
            document.getElementById("printer").value,
            document.getElementById("filament").value,
            document.getElementById("magnification").value,
            document.getElementById("temperature").value
        ];

        const content = fields.join(', '); // Join all field values with comma and space

        const blob = new Blob([content], { type: 'text/plain' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'assembly_config.txt';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    },

    skip_config: function() {
      this.stepValue = this.stepValue + 2;
    },
    complete_config: function() {
      this.stepValue = this.stepValue + 1;
    }
  }
};
</script>

<style scoped>
.mini-preview {
  width: 75%;
  margin-left: auto;
  margin-right: auto;
}
textarea {
  resize: none;
}
.parent {
  text-align: left;
}
.child {
  display: inline-block;
  padding: 1rem 1rem;
}
.centre {
  justify-content: center;
  display: flex;
  align-items: center;
  padding: 20px;
}
</style>
