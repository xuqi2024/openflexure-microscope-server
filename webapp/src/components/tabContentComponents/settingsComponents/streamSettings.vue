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
        return this.$store.state.disableStream;
      },
      set(value) {
        this.$store.commit("changeDisableStream", value);
      }
    }
  },

  watch: {
    // Cache the stream settings to local storage for persistence
    // (the next 3 functions all relate to this)
    disableStream: function(newValue) {
      this.setLocalStorageObj("disableStream", newValue);
    }
  }
};
</script>

<style lang="less"></style>
