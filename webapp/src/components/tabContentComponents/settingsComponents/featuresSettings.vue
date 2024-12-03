<template>
  <div id="appSettings" class="uk-width-large">
    <h3>Additional features</h3>
    <p class="uk-margin-small" :class="{ 'uk-text-muted': !imjoyPermitted }">
      <label :disabled="!imjoyPermitted">
        <input
          v-model="imjoyEnabled"
          class="uk-checkbox"
          type="checkbox"
          :disabled="!imjoyPermitted"
        />
        Enable ImJoy plugin engine
      </label>
    </p>
    <p v-if="imjoyPermitted" class="uk-margin-small">
      <a href="https://imjoy.io/">ImJoy</a> enables integration with a wide
      variety of microscopy and image analysis applications, including ImageJ.JS
      and Kaibu. Support for ImJoy within the OFM software is currently
      experimental, and it may slow down loading of the application.
    </p>
    <p v-if="!imjoyPermitted" class="uk-margin-small uk-text-muted">
      ImJoy plugins are disabled in this build of the OpenFlexure software.
    </p>
    <p class="uk-margin-small">
      <label
        ><input v-model="galleryEnabled" class="uk-checkbox" type="checkbox" />
        Enable Gallery</label
      >
    </p>
    <p class="uk-margin-small">
      The "gallery" tab can cause performance issues; un-tick the box above to
      disable it.
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
    imjoyEnabled: {
      get() {
        return this.$store.state.imjoyEnabled;
      },
      set(value) {
        this.$store.commit("changeImjoyEnabled", value);
      }
    },
    galleryEnabled: {
      get() {
        return this.$store.state.galleryEnabled;
      },
      set(value) {
        this.$store.commit("changeGalleryEnabled", value);
      }
    },
    imjoyPermitted: function() {
      // ImJoy may be disabled using an environment variable.
      // If this function returns false, it is never possible to
      // use ImJoy, so we should gray out the option.
      return process.env.VUE_APP_ENABLE_IMJOY === "true";
    }
  },

  watch: {
    imjoyEnabled: function() {
      this.setLocalStorageObj("imjoyEnabled", this.imjoyEnabled);
    },
    galleryEnabled: function() {
      this.setLocalStorageObj("galleryEnabled", this.galleryEnabled);
    }
  },

  mounted() {
    // Try loading settings from localStorage. If null, don't change.
    this.imjoyEnabled =
      this.getLocalStorageObj("imjoyEnabled") || this.imjoyEnabled;
    this.galleryEnabled =
      this.getLocalStorageObj("galleryEnabled") || this.galleryEnabled;
  }
};
</script>

<style lang="less"></style>
