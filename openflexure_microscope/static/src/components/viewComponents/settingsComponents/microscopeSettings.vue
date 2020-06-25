<template>
  <div v-if="settings" id="microscopeSettings">
    <form @submit.prevent="applyConfigRequest">
      <label class="uk-form-label" for="form-stacked-text"
        >Backlash compensation</label
      >
      <div class="uk-grid-small uk-child-width-1-3" uk-grid>
        <div>
          <label class="uk-form-label" for="form-stacked-text">x</label>
          <div class="uk-form-controls">
            <input
              v-model="settings.stage.backlash.x"
              class="uk-input uk-form-small"
              type="number"
            />
          </div>
        </div>

        <div>
          <label class="uk-form-label" for="form-stacked-text">y</label>
          <div class="uk-form-controls">
            <input
              v-model="settings.stage.backlash.y"
              class="uk-input uk-form-small"
              type="number"
            />
          </div>
        </div>

        <div>
          <label class="uk-form-label" for="form-stacked-text">z</label>
          <div class="uk-form-controls">
            <input
              v-model="settings.stage.backlash.z"
              class="uk-input uk-form-small"
              type="number"
            />
          </div>
        </div>
      </div>

      <br />

      <div>
        <label class="uk-form-label" for="form-stacked-text"
          >Microscope name</label
        >
        <input
          v-model="settings.name"
          class="uk-input uk-width-1-1 uk-form-small"
          name="inputFilename"
          placeholder="Leave blank for default"
        />
      </div>

      <br />

      <button
        type="submit"
        class="uk-button uk-button-primary uk-form-small uk-float-right uk-margin-small uk-width-1-1"
      >
        Apply Settings
      </button>
    </form>
  </div>
</template>

<script>
import axios from "axios";

// Export main app
export default {
  name: "MicroscopeSettings",

  data: function() {
    return {
      settings: null
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
          this.settings = response.data;
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    applyConfigRequest: function() {
      var payload = {
        name: this.settings.name,
        stage: {
          backlash: this.settings.stage.backlash
        }
      };

      console.log(payload);

      // Send request to update config
      axios
        .put(this.settingsUri, payload)
        .then(() => {
          // Update local settings
          this.updateSettings();
          this.modalNotify("Microscope settings applied.");
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    }
  }
};
</script>

<style lang="less">
.center-spinner {
  margin-left: auto;
  margin-right: auto;
}
</style>
