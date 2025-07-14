<template>
  <!-- Grid managing tab content -->
  <div class="container">
    <h1 id="power-title"> Power</h1>
    <p id="power-msg"> It's essential to turn off your OpenFlexure Microscope here before unplugging it.
    <br>
    <br>
    Unplugging the microscope unexpectedly can damage the SD card or onboard computer.
    </p>
    <div class="buttons-container">
      <button
        v-show="'shutdown' in things.system.actions"
        class="uk-button uk-button-primary uk-width-1-3 shutdown-button"
        @click="systemRequest('shutdown')"
      >
        Shutdown
      </button>
      <button
        v-if="isRaspberrypi"
        class="uk-button uk-button-primary uk-width-1-3 shutdown-button"
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

  data: function() {
    return {
      isRaspberrypi: undefined,
    }
  },
  
  computed: {
    things: function() {
      return this.$store.getters["wot/thingDescriptions"];
    }
  },

  async mounted() {
    this.isRaspberrypi = await this.readThingProperty(
      "system",
      "is_raspberrypi"
    );
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
            .post(this.thingActionUrl("system", action))
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


.container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  padding: 2em;
  box-sizing: border-box;
}

#power-title {
  text-align: center;
}

#power-msg {
  text-align: center;
}

.buttons-container {
  width: 100%;
  text-align: center;
}

.shutdown-button {
  display: inline;
  text-align:center;
  margin: 30px 30px 30px 30px;
}
</style>