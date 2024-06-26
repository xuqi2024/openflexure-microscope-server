<template>
  <div class="uk-padding-small">
    <div v-show="!backendOK" class="uk-alert-danger">
      The stage calibration detect Thing seems to be missing or incompatible.
    </div>
    <div v-show="backendOK">
      <div class="uk-margin">
        <action-button
          thing="range_of_motion"
          action="measure_rom"
          submit-label="Measure range of motion"
          :can-terminate="true"
          :requires-confirmation="true"
          :modal-progress="true"
          :confirmation-message="
          'The stage will now move, measuring the stage range of motion. This requires a sample to be visible '
          + 'in the microscope big enough to cover the full range of motion, and the stage to be roughly centred. OK to proceed?'
          "
          :poll-interval="0.1"
          @response="alertROMMeasured"
        />
      </div>
      <div class="uk-margin">
        <action-button
          thing="auto_recentre_stage"
              action="recentre"
              submit-label="Re-centre Stage"
              :can-terminate="true"
              :requires-confirmation="true"
              :modal-progress="true"
              :confirmation-message="
                'The stage will now move, and autofocus will be used to find the centre of motion. This requires a sample to be visible in the microscope. OK to proceed?'
              "
          :submit-data="{max_steps: 15,  lateral_distance: 2500}"
        />
      </div>
      <button
      type="button"
      class="uk-button uk-button-default uk-width-1-1"
      @click="getStageData()"
    >
      Download calibration data
    </button>
    <div class="uk-margin">
        <action-button
          thing="autofocus"
              action="autofocus_report"
              submit-label="Test autofocus"
              :can-terminate="true"
              :requires-confirmation="true"
              :modal-progress="true"
              :modal-response="true"
              :confirmation-message="
                'A series of autofocuses will now run, and the success of each will be measured. The resulting plots can be downloaded from the logs folder. OK to proceed?'
              "
          :submit-data="{repeats: 20,  plots: 'true'}"
        />
      </div>
    </div>
  </div>
</template>

<script>
import ActionButton from "../../labThingsComponents/actionButton.vue";

export default {
  name: "paneStage",

  components: {
    ActionButton
  },

  computed: {
    backendOK() {
      return this.thingAvailable("range_of_motion");
    }
  },

  methods: {
    alertROMMeasured() {
      this.modalNotify(`Range of motion has been measured`);
    },

    getStageData: async function() {
      try {
        let recentre_data = await this.readThingProperty(
          "auto_recentre_stage",
          "recentring_data")
        let rom_data = await this.readThingProperty(
          "range_of_motion",
          "rom_data"
        );
        var data = Object.assign({}, rom_data, recentre_data)
        if (data == {}) {
          throw "No calibration data available.";
        }
        const dataStr = JSON.stringify(data);
        const url = window.URL.createObjectURL(new Blob([dataStr]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", "stage_data.json");
        document.body.appendChild(link);
        link.click();
      } catch (error) {
        this.modalError(error); // Let mixin handle error
      }
    },
  }
};
</script>
