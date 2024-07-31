<template>
  <div id="appSettings" class="uk-width-large">
    <h3>Appearance</h3>
    <p>
      <label>
        Theme
        <select v-model="appTheme" class="uk-select">
          <option value="light">Light</option>
          <option value="dark">Dark</option>
          <option value="system">System</option>
        </select>
      </label>
    </p>
  </div>
</template>

<script>
// Export main app
export default {
  name: "AppSettings",

  data: function() {
    return {};
  },

  computed: {
    appTheme: {
      get() {
        return this.$store.state.appTheme;
      },
      set(value) {
        this.$store.commit("changeAppTheme", value);
      }
    }
  },

  watch: {
    appTheme: function() {
      this.setLocalStorageObj("appTheme", this.appTheme);
    }
  },

  mounted() {
    // Try loading settings from localStorage. If null, don't change.
    this.appTheme = this.getLocalStorageObj("appTheme") || this.appTheme;
  }
};
</script>

<style lang="less"></style>
