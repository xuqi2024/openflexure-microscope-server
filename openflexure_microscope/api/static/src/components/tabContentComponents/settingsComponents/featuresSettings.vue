<template>
  <div id="appSettings" class="uk-width-large">
    <h3>Additional features</h3>
    <p class="uk-margin-small">
      <label
        ><input v-model="IHIEnabled" class="uk-checkbox" type="checkbox" />
        Enable IHI Slide Scan</label
      >
    </p>
    <p class="uk-margin-small">
      Enabling IHI Slide Scan will add a new tab designed to simplify acquiring
      blood smear tile scans. <br />
      While this may be useful for other applications, it is primarily designed
      for use in clinics acquiring blood smear samples using a 100x
      oil-immersion objective, with a Raspberry Pi Camera v2.
    </p>
  </div>
</template>

<script>
// Export main app
export default {
  name: "FeaturesSettings",

  data: function() {
    return {};
  },

  computed: {
    IHIEnabled: {
      get() {
        return this.$store.state.IHIEnabled;
      },
      set(value) {
        this.$store.commit("changeIHIEnabled", value);
        this.$emitter.emit("globalSafeTogglePreview", value);
      }
    }
  },

  watch: {
    IHIEnabled() {
      this.setLocalStorageObj("IHIEnabled", this.IHIEnabled);
    }
  },

  mounted() {
    // Try loading settings from localStorage. If null, don't change.
    this.IHIEnabled = this.getLocalStorageObj("IHIEnabled") || this.IHIEnabled;
  }
};
</script>

<style lang="less"></style>
