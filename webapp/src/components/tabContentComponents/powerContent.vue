<template>
  <!-- Grid managing tab content -->
  <div class="center">
  <h1 style="text-align: center;"> Power</h1>
  <p style="text-align: center;"> It's essential to turn off your OpenFlexure Microscope here before unplugging it.
  <br>
  <br>
  Unplugging the microscope unexpectedly can damage the SD card or onboard computer.
  </p>
    <div class="buttons">
      <button
        v-show="'shutdown' in things.system_control.actions"
        class="uk-button uk-button-primary uk-width-1-3"
        @click="systemRequest('shutdown')"
      >
        Shutdown
      </button>
      <button
        v-show="'reboot' in things.system_control.actions"
        class="uk-button uk-button-primary uk-width-1-3"
        @click="systemRequest('reboot')"
      >
        Restart
      </button>
    </div>
  </div>
</template>

<script>
import axios from "axios";

export default {
  name: "PowerContent",

  components: {},
  
  computed: {
    things: function() {
      return this.$store.getters["wot/thingDescriptions"];
    }
  },

  methods: {
  systemRequest: function(action) {
      let message = "";
      if (action == "reboot") {
        message = "Restart microscope?"
      }
      else {
        message = "Shutdown microscope?"
      }
      this.modalConfirm(message).then(
        () => {
          this.$store.commit("resetState");
          this.$store.commit("wot/deleteAllThingDescriptions");
          // Post and silence errors
          axios
            .post(this.thingActionUrl("system_control", action))
            .catch(() => {});
        },
        () => {}
      );
    }
  }
};
</script>

<style lang="less" scoped>
// Custom UIkit CSS modifications
@import "../../assets/less/theme.less";

.center {
    right: 50%;
    bottom: 50%;
    transform: translate(50%,50%);
    position: absolute;
}

.uk-button {
  display: inline;
  text-align:center;
  margin: 30px 30px 30px 30px;
}
</style>