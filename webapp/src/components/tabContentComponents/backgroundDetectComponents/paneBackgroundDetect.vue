<template>
  <div class="uk-padding-small">
    <div v-show="!backendOK" class="uk-alert-danger">
      The background detect Thing seems to be missing or incompatible.
    </div>
    <div v-show="backendOK">
      <ul uk-accordion="multiple: true">
        <li>
          <a class="uk-accordion-title" href="#">Settings</a>
          <div class="uk-accordion-content">
            <div class="uk-margin">
              <propertyControl
                thing-name="background_detect"
                property-name="tolerance"
                label="Tolerance"
              />
            </div>
            <div class="uk-margin">
              <propertyControl
                thing-name="background_detect"
                property-name="fraction"
                label="Sample coverage required (%)"
              />
            </div>
            <div class="uk-margin">
              <action-button
                thing="background_detect"
                action="background_fraction"
                submit-label="Check coverage"
                :can-terminate="false"
                :poll-interval="0.1"
                @response="alertBackgroundFraction"
                @error="backgroundDetectError"
              />
            </div>
          </div>
        </li>
      </ul>
      <div class="uk-margin">
        <action-button
          thing="background_detect"
          action="set_background"
          submit-label="Set background"
          :can-terminate="false"
          :poll-interval="0.1"
          @response="alertBackgroundSet"
        />
      </div>
      <div class="uk-margin">
        <action-button
          thing="background_detect"
          action="image_is_sample"
          submit-label="Check current image"
          :can-terminate="false"
          :poll-interval="0.1"
          @response="alertImageLabel"
          @error="backgroundDetectError"
        />
      </div>
    </div>
  </div>
</template>

<script>
import ActionButton from "../../labThingsComponents/actionButton.vue";
import propertyControl from "../../labThingsComponents/propertyControl.vue";

export default {
  components: {
    ActionButton,
    propertyControl
  },

  computed: {
    backendOK() {
      return this.thingAvailable("background_detect");
    }
  },

  methods: {
    alertBackgroundFraction(r) {
      let fraction = r.output;
      // let percentage = (fraction * 100).toFixed(0);
      this.modalNotify(`Current image is ${fraction.toFixed(0)}% background.`);
    },
    alertBackgroundSet() {
      this.modalNotify(`Background image has been updated`);
    },
    alertImageLabel(r) {
      let label = r.output === true ? "sample" : "background";
      this.modalNotify(`Current image is ${label}`);
    },
    backgroundDetectError() {
      this.modalError(
        "Background detection failed, most likely you need to set a background image." +
          " There may be more information in the log."
      );
    }
  }
};
</script>
