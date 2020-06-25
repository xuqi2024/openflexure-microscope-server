<template>
  <div id="streamSettings">
    <div>
      <h3>Stream settings</h3>
      <label
        ><input v-model="disableStream" class="uk-checkbox" type="checkbox" />
        Disable live stream</label
      >
    </div>

    <br />

    <div>
      <h3>Microscope display output</h3>
      <div uk-grid>
        <div>
          <label :class="[{ 'uk-disabled': !this.$store.getters.ready }]"
            ><input
              v-model="autoGpuPreview"
              class="uk-checkbox"
              type="checkbox"
            />
            Enable GPU preview</label
          >
        </div>
        <div>
          <label :class="[{ 'uk-disabled': !this.$store.getters.ready }]"
            ><input v-model="trackWindow" class="uk-checkbox" type="checkbox" />
            Track window</label
          >
        </div>
      </div>
    </div>
  </div>
</template>

<script>
// Export main app
export default {
  name: "StreamSettings",

  data: function() {
    return {};
  },

  computed: {
    disableStream: {
      get() {
        return this.$store.state.globalSettings.disableStream;
      },
      set(value) {
        this.$store.commit("changeSetting", ["disableStream", value]);
      }
    },

    autoGpuPreview: {
      get() {
        return this.$store.state.globalSettings.autoGpuPreview;
      },
      set(value) {
        this.$store.commit("changeSetting", ["autoGpuPreview", value]);
        this.$root.$emit("globalSafeTogglePreview", value);
      }
    },

    trackWindow: {
      get() {
        return this.$store.state.globalSettings.trackWindow;
      },
      set(value) {
        this.$store.commit("changeSetting", ["trackWindow", value]);
      }
    }
  }
};
</script>

<style lang="less"></style>
