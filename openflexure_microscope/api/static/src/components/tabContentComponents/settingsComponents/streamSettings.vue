<template>
  <div id="streamSettings" class="uk-width-large">
    <div>
      <h3>Stream settings</h3>
      <label
        ><input v-model="disableStream" class="uk-checkbox" type="checkbox" />
        Disable web stream</label
      >
      <p class="uk-margin-small">
        This will disable the embedded web stream of the camera.
      </p>
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
      <p>
        Enable GPU preview turns on a low-latency camera preview drawn directly
        to the Raspberry Pi display output.
      </p>
      <p class="uk-margin-small">
        <b
          >Content, such as your mouse, won't be visible behind this preview.</b
        >
        Track Window will attempt to resize the GPU preview based on the current
        window size, however this is often imperfect and cannot track window
        movement.
      </p>
    </div>
  </div>
</template>

<script>
// Export main app
export default {
  name: "StreamSettings",

  data: function () {
    return {};
  },

  computed: {
    disableStream: {
      get() {
        return this.$store.state.disableStream;
      },
      set(value) {
        this.$store.commit("changeDisableStream", value);
      },
    },

    autoGpuPreview: {
      get() {
        return this.$store.state.autoGpuPreview;
      },
      set(value) {
        this.$store.commit("changeAutoGpuPreview", value);
        this.$root.$emit("globalSafeTogglePreview", value);
      },
    },

    trackWindow: {
      get() {
        return this.$store.state.trackWindow;
      },
      set(value) {
        this.$store.commit("changeTrackWindow", value);
      },
    },
  },
};
</script>

<style lang="less"></style>
