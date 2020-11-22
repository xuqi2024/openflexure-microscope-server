<template>
  <div class="uk-padding-small">
    <div v-show="!scanUri">No scan extension found</div>
    <div v-show="scanUri">
      <form @submit.prevent @keyup.enter="increment()">
        <div v-show="stepValue == 0" id="step-user">
          <h3>User information (1/4)</h3>

          <label for="username">Your name:</label>
          <input
            id="username"
            v-model="username"
            class="uk-input"
            type="text"
            name="username"
            required
          />
          <br />
          <label for="currentTime">Current time (check this is correct):</label>
          <input
            id="currentTime"
            v-model="currentTimeForm"
            class="uk-input"
            type="datetime-local"
            name="currentTime"
          />
        </div>

        <div v-show="stepValue == 1" id="step-patient">
          <h3>Patient information (2/4)</h3>

          <label for="patientID">Patient ID:</label>
          <input
            id="patientID"
            v-model="patientID"
            class="uk-input"
            type="text"
            name="patientID"
            required
          />
          <br />
        </div>

        <div v-show="stepValue == 2" id="step-sample">
          <h3>Sample information (3/4)</h3>

          <label>Sample type:</label>
          <br />
          <input
            id="typeThin"
            v-model="sampleType"
            class="uk-radio"
            type="radio"
            value="thin"
          />
          <label for="typeThin">Thin smear</label>
          <br />
          <input
            id="typeThick"
            v-model="sampleType"
            class="uk-radio"
            type="radio"
            value="thick"
          />
          <label for="typeThick">Thick smear</label>
          <br />
        </div>

        <div v-show="stepValue == 3" id="step-scan">
          <h3>Start scan (4/4)</h3>

          <label>Check details:</label>
          <p>
            <b>Your name:</b>
            {{ username }}
          </p>
          <p>
            <b>Patient ID:</b>
            {{ patientID }}
          </p>
          <p>
            <b>Sample type:</b>
            {{ sampleType }}
          </p>
        </div>
      </form>

      <div id="form-stepper">
        <p class="warning">
          {{ message }}
        </p>
        <taskSubmitter
          v-if="scanUri"
          v-show="stepValue == 3"
          :submit-url="scanUri"
          :submit-data="payload"
          submit-label="Start scan"
          @submit="scanRunning = true"
          @response="scanRunning = false"
          @error="scanRunning = false"
        />
        <br />

        <div v-show="!scanRunning" class="grid-container">
          <button
            class="uk-button uk-button-primary"
            :disabled="stepValue <= 0"
            type="button"
            @click="decrement()"
          >
            Previous
          </button>
          <button
            class="uk-button uk-button-primary"
            :disabled="stepValue >= 3"
            type="button"
            @click="increment()"
          >
            Next
          </button>
        </div>
        <p>
          <button
            v-show="stepValue == 3 && !scanRunning"
            class="uk-button uk-button-danger uk-width-1-1"
            :disabled="scanRunning"
            type="button"
            @click="restart()"
          >
            Restart
          </button>
        </p>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import taskSubmitter from "../../genericComponents/taskSubmitter";

export default {
  components: {
    taskSubmitter,
  },

  data: function () {
    return {
      scanUri: null,
      stepValue: 0,
      hostDeviceName: null,
      message: null,
      // Scan info
      username: "",
      currentTime: this.getLocalDatetimeString(),
      patientID: "",
      sampleType: "thin",
      scanRunning: false,
      // Scan settings
      bayer: false,
      grid: [10, 10, 9],
      strideSize: [800, 600, 10],
      fastAutofocus: true,
      autofocusDz: 2000,
      useVideoPort: false,
    };
  },

  computed: {
    pluginsUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/extensions`;
    },
    currentTimeForm: {
      get() {
        // Chop the timezone information from the end
        return this.currentTime.substr(0, 19);
      },
      set(val) {
        console.log(val);
        // Get timezone
        const dt = new Date();
        const tzo = -dt.getTimezoneOffset(),
          dif = tzo >= 0 ? "+" : "-",
          pad = function (num) {
            const norm = Math.floor(Math.abs(num));
            return (norm < 10 ? "0" : "") + norm;
          };
        // Stick to the end of the new timestring from the form
        this.currentTime = val + dif + pad(tzo / 60) + ":" + pad(tzo % 60);
      },
    },

    payload: {
      get() {
        const payload = {};

        payload["filename"] = `${this.patientID}_${this.sampleType}`;
        payload["temporary"] = false;
        payload["bayer"] = this.bayer;
        payload["grid"] = this.grid;
        payload["stride_size"] = this.strideSize;
        payload["fast_autofocus"] = this.fastAutofocus;
        payload["autofocus_dz"] = this.autofocusDz;
        payload["use_video_port"] = this.useVideoPort;
        payload["annotations"] = {
          patientID: this.patientID,
          username: this.username,
          clientDatetime: this.currentTime,
        };
        payload["tags"] = ["slidescan"];

        return payload;
      },
    },
  },

  mounted: function () {
    this.updateScanUri();
  },

  methods: {
    updateScanUri: function () {
      axios
        .get(this.pluginsUri) // Get a list of plugins
        .then((response) => {
          const plugins = response.data;
          const foundExtension = plugins.find(
            (e) => e.title === "org.openflexure.scan"
          );
          // if ScanPlugin is enabled
          if (foundExtension) {
            // Get plugin action link
            this.scanUri = foundExtension.links.tile.href;
          }
        })
        .catch((error) => {
          this.modalError(error); // Let mixin handle error
        });
    },

    decrement: function () {
      if (this.stepValue > 0) {
        this.stepValue = this.stepValue - 1;
      }
    },

    increment: function () {
      // Validate sections
      if (this.stepValue == 0) {
        if (!this.username) {
          this.message = "Please enter your name";
          return false;
        }
      }
      if (this.stepValue == 1) {
        if (!this.patientID) {
          this.message = "Please enter a patient ID";
          return false;
        }
      }
      // Upper bound on section number
      if (this.stepValue < 3) {
        this.stepValue = this.stepValue + 1;
        this.message = "";
        return true;
      }
    },

    restart: function () {
      this.stepValue = 0;
      this.patientID = "";
      this.currentTime = this.getLocalDatetimeString();
    },

    getLocalDatetimeString: function () {
      const dt = new Date();
      const tzo = -dt.getTimezoneOffset(),
        dif = tzo >= 0 ? "+" : "-",
        pad = function (num) {
          const norm = Math.floor(Math.abs(num));
          return (norm < 10 ? "0" : "") + norm;
        };
      return (
        dt.getFullYear() +
        "-" +
        pad(dt.getMonth() + 1) +
        "-" +
        pad(dt.getDate()) +
        "T" +
        pad(dt.getHours()) +
        ":" +
        pad(dt.getMinutes()) +
        ":" +
        pad(dt.getSeconds()) +
        dif +
        pad(tzo / 60) +
        ":" +
        pad(tzo % 60)
      );
    },
  },
};
</script>

<style>
.grid-container {
  display: grid;
  grid-template-columns: auto auto;
  grid-column-gap: 10px;
}

.warning {
  color: #c11;
  font-weight: bold;
  text-align: center;
}
</style>
