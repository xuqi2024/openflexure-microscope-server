<template>
  <a
    href="#"
    class="uk-link"
    :class="classObject"
    :uk-tooltip="tooltipOptions"
    @click="setThisTab"
  >
    <slot></slot>
    <div v-if="showTitle" class="tabtitle">
      {{ computedTitle }}
    </div>
  </a>
</template>

<script>
export default {
  name: "TabIcon",

  props: {
    tabID: {
      type: String,
      required: true
    },
    title: {
      type: String,
      required: false,
      default: undefined
    },
    showTitle: {
      type: Boolean,
      required: false,
      default: true
    },
    showTooltip: {
      type: Boolean,
      required: false,
      default: true
    },
    currentTab: {
      type: String,
      required: true
    },
    clickCallback: {
      type: Function,
      required: false,
      default: null
    },
    requireConnection: Boolean
  },

  computed: {
    computedTitle: function() {
      if (this.title !== undefined) {
        return this.title;
      } else {
        // Get the last section of a fully qualified name
        const topName = this.tabID.split(".").pop();
        // Make first character uppercase, then add the rest of the string
        return topName.charAt(0).toUpperCase() + topName.slice(1);
      }
    },

    tooltipOptions: function() {
      if (this.showTooltip) {
        return `pos: right; title: ${this.computedTitle}; delay: 500`;
      } else {
        return false;
      }
    },

    classObject: function() {
      return {
        "tabicon-active": this.currentTab == this.tabID,
        "uk-disabled": this.requireConnection && !this.$store.getters.ready
      };
    }
  },

  methods: {
    setThisTab(event) {
      this.$emit("set-tab", event, this.tabID);
      if (this.clickCallback) {
        this.clickCallback();
      }
    }
  }
};
</script>

<style lang="less" scoped>
// Custom UIkit CSS modifications
@import "../../assets/less/theme.less";

.tabicon-active {
  color: #fff !important;
  background-color: @global-primary-background !important;
}

.tabtitle {
  max-width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 85%;
}

a:hover,
.uk-link:hover {
  text-decoration: none !important;
}
</style>
