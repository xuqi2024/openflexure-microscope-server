<template>
  <!-- Grid managing tab content -->

  <div class="view-component uk-height-1-1 uk-width-expand">
    <galleryDisplay />
  </div>
</template>

<script>
import galleryDisplay from "../viewComponents/galleryDisplay.vue";

export default {
  name: "NavigateContent",

  components: {
    galleryDisplay
  }
};
</script>
