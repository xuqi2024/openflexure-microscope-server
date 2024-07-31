<template>
  <div>
    <form
      class="uk-form-stacked"
      action=""
      method="GET"
      @submit="overrideAPIHost"
    >
      <label class="uk-form-label">Override API origin</label>
      <input
        v-model="newOrigin"
        name="overrideOrigin"
        class="uk-input"
        type="text"
      />
      <label class="uk-form-label">
        <input
          v-model="reloadWhenOverridingOrigin"
          class="uk-input uk-checkbox"
          type="checkbox"
        />
        Reload web app with new origin
      </label>
      <button class="uk-button uk-button-default uk-margin-small">
        Apply
      </button>
    </form>
    <form class="uk-form-stacked" @submit.prevent="resetTour">
      <label class="uk-form-label">Re-run tour on next load</label>
      <button class="uk-button uk-button-default uk-margin-small">
        Reset
      </button>
    </form>
  </div>
</template>

<script>
// Export main app
export default {
  name: "DevTools",

  components: {},

  data: function() {
    return {
      newOrigin: this.$store.state.origin,
      reloadWhenOverridingOrigin: true
    };
  },

  mounted() {
    if (localStorage.overrideOrigin) {
      this.newOrigin = localStorage.overrideOrigin;
    } else {
      this.newOrigin = "http://microscope.local:5000";
    }
  },

  methods: {
    overrideAPIHost: function(event) {
      // Save the origin override, so that if we reload the web app, you can easily
      localStorage.overrideOrigin = this.newOrigin;

      // If we have elected not to reload the interface, just update the origin
      // in the store.  Otherwise, the form's default action will do the job for us.
      // TODO: preserve other query parameters when reloading
      if (!this.reloadWhenOverridingOrigin) {
        this.$store.commit("changeOrigin", this.newOrigin);
        event.preventDefault();
      }
    },
    resetTour: function() {
      // Make the introduction tour run next time the app loads
      this.setLocalStorageObj("completedTour", false);
    }
  }
};
</script>

<style scoped lang="less">
.error-icon {
  font-size: 120px;
}
</style>
