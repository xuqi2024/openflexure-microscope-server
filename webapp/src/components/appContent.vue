<template>
  <div
    id="app-content"
    class="uk-margin-remove uk-padding-remove uk-height-1-1"
    uk-grid
  >
    <!-- Initialisation modals -->
    <calibrationModal
      ref="calibrationModal"
      @onClose="enterApp()"
    ></calibrationModal>
    <!-- Vertical tab bar -->
    <div id="switcher-left-container">
      <div
        id="switcher-left"
        class="uk-flex uk-flex-column uk-padding-remove uk-width-auto uk-height-1-1 uk-text-center"
      >
        <!-- For each top tab -->
        <template v-for="(item, index) in topTabs">
          <!-- Render the tab icon -->
          <tabIcon
            :id="item.id + '-tab-icon'"
            :key="item.id + '-tab-icon'"
            :tab-i-d="item.id"
            :require-connection="true"
            :current-tab="currentTab"
            :class="item.class"
            @set-tab="setTab"
          >
            <img
              v-if="item.iconURL"
              style="filter: grayscale(100%);width: 22px;margin-top: 5px;margin-bottom: 8px;"
              :src="item.iconURL"
            />
            <span v-if="!item.iconURL" class="material-symbols-outlined">
              {{ item.icon }}
            </span>
          </tabIcon>
          <!-- Add a divider if item.divide is true -->
          <hr v-if="item.divide" :key="'tab-divider-' + index" />
        </template>

        <tabIcon
          v-for="imjoyTab in imjoyTabs"
          :key="imjoyTab.id"
          :tab-i-d="'ImJoy-Plugin-' + imjoyTab.id"
          :title="imjoyTab.name"
          :require-connection="false"
          :current-tab="currentTab"
          @set-tab="setTab"
        >
          <img
            v-if="imjoyTab.iconURL"
            style="filter: grayscale(100%);width: 22px;margin-top: 5px;margin-bottom: 8px;"
            :src="imjoyTab.iconURL"
          />
          <span v-if="!imjoyTab.iconURL" class="material-symbols-outlined">
            {{ imjoyTab.iconName || "extension" }}
          </span>
        </tabIcon>

        <hr id="extension-tab-divider" />

        <!-- For each bottom tab -->
        <template v-for="(item, index) in bottomTabs">
          <!-- Render the tab icon -->
          <tabIcon
            :id="item.id + '-tab-icon'"
            :key="item.id + '-tab-icon'"
            :tab-i-d="item.id"
            :require-connection="true"
            :current-tab="currentTab"
            :class="item.class"
            @set-tab="setTab"
          >
            <span class="material-symbols-outlined">{{ item.icon }}</span>
          </tabIcon>
          <!-- Add a divider if item.divide is true -->
          <hr v-if="item.divide" :key="'tab-divider-' + index" />
        </template>
      </div>
    </div>

    <!-- Corresponding vertical tab content -->
    <div
      id="container-left"
      class="uk-padding-remove uk-height-1-1 uk-width-expand"
    >
      <!-- For each top tab -->
      <tabContent
        v-for="item in topTabs"
        :id="item.id + '-tab-content'"
        :key="item.id + '-tab-content'"
        :tab-i-d="item.id"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <component :is="item.component"></component>
      </tabContent>

      <tabContent
        v-for="imjoyTab in imjoyTabs"
        :key="imjoyTab.id"
        :tab-i-d="'ImJoy-Plugin-' + imjoyTab.id"
        :require-connection="false"
        :current-tab="currentTab"
      >
        <div :id="imjoyTab.window_id" class="window-container">Loading...</div>
      </tabContent>

      <!-- For each bottom tab -->
      <tabContent
        v-for="item in bottomTabs"
        :id="item.id + '-tab-content'"
        :key="item.id + '-tab-content'"
        :tab-i-d="item.id"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <component :is="item.component"></component>
      </tabContent>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";

// Import generic components
import tabIcon from "./genericComponents/tabIcon";
import tabContent from "./genericComponents/tabContent";

// Import new content components
import navigateContent from "./tabContentComponents/navigateContent.vue";
import slideScanContent from "./tabContentComponents/slideScanContent.vue";
import backgroundDetectContent from "./tabContentComponents/backgroundDetectContent.vue";
import viewContent from "./tabContentComponents/viewContent.vue";
import settingsContent from "./tabContentComponents/settingsContent.vue";
import aboutContent from "./tabContentComponents/aboutContent.vue";
import loggingContent from "./tabContentComponents/loggingContent.vue";
// ImJoy is loaded asynchronously to allow it to be disabled if needed
const imjoyContent = () =>
  import(
    /* webpackChunkName: "imjoy" */ "./tabContentComponents/imjoyContent.vue"
  );

// Import modal components for device initialisation
import calibrationModal from "./modalComponents/calibrationModal.vue";
import TabIcon from "./genericComponents/tabIcon.vue";
import ScanListContent from "./tabContentComponents/scanListContent.vue";

// Export main app
export default {
  name: "AppContent",

  components: {
    tabIcon,
    tabContent,
    navigateContent,
    slideScanContent,
    viewContent,
    settingsContent,
    calibrationModal,
    aboutContent,
    loggingContent,
    TabIcon,
    imjoyContent
  },
  data: function() {
    return {
      currentTab: "view",
      bottomTabs: [
        {
          id: "settings",
          icon: "settings",
          component: settingsContent,
          class: "uk-margin-auto-top"
        },
        {
          id: "logging",
          icon: "assignment_late",
          component: loggingContent
        },
        {
          id: "about",
          icon: "info",
          component: aboutContent
        }
      ]
    };
  },

  computed: {
    tabOrder: function() {
      var ind = [];
      for (const tab of this.topTabs) {
        ind.push(tab.id);
      }
      for (const tab of this.bottomTabs) {
        ind.push(tab.id);
      }
      return ind;
    },

    topTabs: function() {
      let tabs = [
        {
          id: "view",
          icon: "visibility",
          component: viewContent
        },
        {
          id: "navigate",
          icon: "gamepad",
          component: navigateContent
        },
        {
          id: "slidescan",
          icon: "settings_overscan",
          component: slideScanContent
        },
        {
          id: "scanlist",
          icon: "photo_library",
          component: ScanListContent
        },
        {
          id: "background_detect",
          icon: "background_replace",
          component: backgroundDetectContent
        }
      ];
      if (!this.$store.state.galleryEnabled) {
        tabs = tabs.filter(tab => tab.id != "gallery");
      }
      if (this.$store.state.imjoyEnabled) {
        tabs.push({
          id: "imjoy",
          iconURL: "https://imjoy.io/static/img/imjoy-icon.svg",
          component: imjoyContent,
          divide: true
        });
      }
      return tabs;
    },

    currentTabIndex: function() {
      return this.tabOrder.indexOf(this.currentTab);
    },

    // Map the tabs from ImJoy's store module so we can display them
    ...mapState("imjoy", { imjoyTabs: "tabs" }),
    ...mapState({ imjoyEnabled: "imjoyEnabled" })
  },

  mounted() {
    // A global signal listener to switch tab
    this.$root.$on("globalSwitchTab", tabID => {
      this.currentTab = tabID;
    });
    // A global signal listener to increment tab
    this.$root.$on("globalIncrementTab", () => {
      this.incrementTabBy(1);
    });
    // A global signal listener to decrement tab
    this.$root.$on("globalDecrementTab", () => {
      this.incrementTabBy(-1);
    });
    if (this.$store.getters.ready) {
      this.startModals();
    }
  },

  methods: {
    setTab: function(event, tab) {
      if (!(this.currentTab == tab)) {
        this.currentTab = tab;
      }
    },
    incrementTabBy: function(n) {
      const newIndex =
        (((this.currentTabIndex + n) % this.tabOrder.length) +
          this.tabOrder.length) %
        this.tabOrder.length;
      const newId = this.tabOrder[newIndex];
      this.currentTab = newId;
    },
    startModals: function() {
      //this.$refs.calibrationModal.show();
    },
    enterApp: function() {
      // Stuff to do once connected and all init modals are finished
    }
  }
};
</script>

<style scoped lang="less">
.window-container {
  width: 100%;
  height: 100%;
}
#component-left {
  width: 100%;
  height: 100%;
}

#container-left {
  overflow: auto;
  background-color: rgba(180, 180, 180, 0.025);
  width: 100%;
  height: 100%;
}

#switcher-left {
  width: 75px;
  padding-top: 2px !important;
}

#switcher-left-container {
  margin: 0;
  padding: 0;
  overflow-x: hidden;
  overflow-y: auto;
  height: 100%;
  background-color: rgba(180, 180, 180, 0.1);
  border-width: 0 1px 0 0;
  border-style: solid;
  border-color: rgba(180, 180, 180, 0.25);
}

#switcher-left a {
  padding: 10px 8px;
}
</style>
