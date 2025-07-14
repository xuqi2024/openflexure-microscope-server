<template>
  <div class="host-input">
    <div v-if="$store.state.available">
      <div>
        <div class="uk-margin-small-bottom">
          <b>Microscope Hostname:</b>
          <br />
          {{ $store.state.microscopeHostname }}
        </div>
        <div class="uk-margin-small-bottom">
          <b>API Origin:</b>
          <br />
          {{ $store.state.origin }}
        </div>
        <action-button
          thing="stage"
          action="flash_led"
          submit-label="Flash Illumination"
          :can-terminate="false"
          :submit-data="{ dt: 0.25 }"
        />
      </div>

      <hr />

      <div>
        <b>Server Version:</b> <br />
        {{ version }}<br />
        ({{ version_source }})
      </div>

      <hr />

      <div class="uk-margin-small-bottom">
        <b>Camera:</b>
        <br />
        <div v-if="'camera' in things">
          {{ things.camera.title }}
        </div>
        <div v-else class="uk-text-danger"><b>No camera configured</b></div>
      </div>
      <div>
        <b>Stage:</b>
        <br />
        <div v-if="'stage' in things">
          {{ things.stage.title }}
        </div>
        <div v-else class="uk-text-danger"><b>No stage configured</b></div>
      </div>

      <hr />
    </div>
    <div v-else-if="$store.state.waiting">
      Loading...
    </div>
    <div v-else-if="$store.state.error">
      <b>Error:</b> {{ $store.state.error }}
    </div>
    <div v-else>No active connection</div>
  </div>
</template>

<script>
import ActionButton from "../../labThingsComponents/actionButton.vue";

export default {
  name: "StatusPane",
  components: { ActionButton },

  data: function() {
    return {
      version: undefined,
      version_source: undefined
    }
  },

  async mounted() {
    let version_data = await this.readThingProperty(
      "system",
      "version_data"
    );
    this.version = version_data.version;
    this.version_source = this.truncate(version_data.version_source);

  },

  computed: {
    things: function() {
      return this.$store.getters["wot/thingDescriptions"];
    }
  },

  methods: {
    truncate(string, max_length=15) {
      if (!(typeof string === 'string' || string instanceof String)) {
        return string;
      }
      if (string.length <= max_length) {
        return string;
      }
      return string.slice(0, max_length - 3) + "...";
    }
  }
};
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped lang="less"></style>
