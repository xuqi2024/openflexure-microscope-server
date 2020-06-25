<template>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="view-component uk-width-expand uk-padding-small">
      <settingsDisplay />
    </div>
  </div>
</template>

<script>
import settingsDisplay from "../viewComponents/settingsDisplay.vue";

export default {
  name: "NavigateContent",

  components: {
    settingsDisplay
  }
};
</script>
