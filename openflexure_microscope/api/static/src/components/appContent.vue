<template>
  <div
    id="app-content"
    class="uk-margin-remove uk-padding-remove uk-height-1-1"
    uk-grid
  >
    <!-- Initialisation modals -->
    <calibrationModal
      ref="calibrationModal"
      :available-plugins="plugins"
      @onClose="enterApp()"
    ></calibrationModal>
    <!-- Vertical tab bar -->
    <div id="switcher-left-container">
      <div
        id="switcher-left"
        class="uk-flex uk-flex-column uk-padding-remove uk-width-auto uk-height-1-1 uk-text-center"
      >
        <!-- For each top tab -->
        <template
          v-for="(item, index) in enabledTopTabs"
          :key="item.id + '-tab-icon'"
        >
          <!-- Render the tab icon -->
          <tabIcon
            :id="item.id + '-tab-icon'"
            :tab-i-d="item.id"
            :require-connection="true"
            :current-tab="currentTab"
            :class="item.class"
            @set-tab="setTab"
          >
            <i class="material-icons">{{ item.icon }}</i>
          </tabIcon>
          <!-- Add a divider if item.divide is true -->
          <hr v-if="item.divide" :key="'tab-divider-' + index" />
        </template>

        <hr id="extension-tab-divider" />

        <!-- For each plugin tab -->
        <tabIcon
          v-for="plugin in pluginsGuiList"
          :key="plugin.id"
          :tab-i-d="plugin.id"
          :title="plugin.title"
          :require-connection="plugin.requiresConnection"
          :current-tab="currentTab"
          :click-callback="updatePlugins"
          @set-tab="setTab"
        >
          <i class="material-icons">{{ plugin.icon || "extension" }}</i>
        </tabIcon>

        <hr id="extension-tab-divider" />

        <!-- For each bottom tab -->
        <template
          v-for="(item, index) in bottomTabs"
          :key="item.id + '-tab-icon'"
        >
          <!-- Render the tab icon -->
          <tabIcon
            :id="item.id + '-tab-icon'"
            :tab-i-d="item.id"
            :require-connection="true"
            :current-tab="currentTab"
            :class="item.class"
            @set-tab="setTab"
          >
            <i class="material-icons">{{ item.icon }}</i>
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
        v-for="item in enabledTopTabs"
        :id="item.id + '-tab-content'"
        :key="item.id + '-tab-content'"
        :tab-i-d="item.id"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <component :is="item.component"></component>
      </tabContent>

      <!-- For each plugin tab -->
      <tabContent
        v-for="plugin in pluginsGuiList"
        :key="plugin.id"
        :tab-i-d="plugin.id"
        :require-connection="plugin.requiresConnection"
        :current-tab="currentTab"
      >
        <extensionContent
          :forms="plugin.forms"
          :frame="plugin.frame"
          :web-component="plugin.wc"
          :view-panel="plugin.viewPanel"
          @reloadForms="updatePlugins()"
        />
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
import axios from "axios";

// Import generic components
import tabIcon from "./genericComponents/tabIcon";
import tabContent from "./genericComponents/tabContent";

// Import new content components
import navigateContent from "./tabContentComponents/navigateContent.vue";
import captureContent from "./tabContentComponents/captureContent.vue";
import slideScanContent from "./tabContentComponents/slideScanContent.vue";
import viewContent from "./tabContentComponents/viewContent.vue";
import settingsContent from "./tabContentComponents/settingsContent.vue";
import galleryContent from "./tabContentComponents/galleryContent.vue";
import extensionContent from "./tabContentComponents/extensionContent.vue";
import aboutContent from "./tabContentComponents/aboutContent.vue";
import loggingContent from "./tabContentComponents/loggingContent.vue";

// Import modal components for device initialisation
import calibrationModal from "./modalComponents/calibrationModal.vue";

// Export main app
export default {
  name: "AppContent",

  components: {
    tabIcon,
    tabContent,
    navigateContent,
    captureContent,
    slideScanContent,
    viewContent,
    settingsContent,
    galleryContent,
    extensionContent,
    calibrationModal,
    aboutContent,
    loggingContent
  },

  data: function() {
    return {
      plugins: [],
      currentTab: "view",
      unwatchStoreFunction: null,
      topTabs: [
        {
          id: "view",
          icon: "visibility",
          component: viewContent
        },
        {
          id: "gallery",
          icon: "photo_library",
          component: galleryContent,
          divide: true // Add a divider after this tab icon
        },
        {
          id: "navigate",
          icon: "gamepad",
          component: navigateContent
        },
        {
          id: "capture",
          icon: "camera_alt",
          component: captureContent,
          divide: true // Add a divider after this tab icon
        }
      ],
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
    enabledTopTabs: function() {
      var enabledTabs = this.topTabs;
      if (this.$store.state.IHIEnabled) {
        enabledTabs.push({
          id: "slidescan",
          icon: "settings_overscan",
          component: slideScanContent
        });
      }
      return enabledTabs;
    },

    pluginsUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/extensions`;
    },

    pluginsGuiList: function() {
      // List of plugin GUIs, obtained from this.plugins values
      var pluginGuis = [];
      for (let plugin of Object.values(this.plugins)) {
        if (plugin.meta.gui) {
          pluginGuis.push(plugin.meta.gui);
        }
      }
      return pluginGuis;
    },

    tabOrder: function() {
      var ind = [];
      for (const tab of this.enabledTopTabs) {
        ind.push(tab.id);
      }
      for (const plugin of this.pluginsGuiList) {
        ind.push(plugin.id);
      }
      for (const tab of this.bottomTabs) {
        ind.push(tab.id);
      }
      return ind;
    },

    currentTabIndex: function() {
      return this.tabOrder.indexOf(this.currentTab);
    }
  },

  created: function() {
    if (this.$store.getters.ready) {
      // Detect local connection
      if (
        ["localhost", "0.0.0.0", "127.0.0.1", "[::1]"].includes(
          window.location.hostname
        )
      ) {
        this.$store.commit("changeDisableStream", true);
        this.$store.commit("changeAutoGpuPreview", true);
        this.$store.commit("changeTrackWindow", true);
      }
      // Update plugins
      this.updatePlugins().then(() => {
        // Start initialisation modals
        this.startModals();
      });
    }
  },

  mounted() {
    // A global signal listener to switch tab
    this.$emitter.on("globalSwitchTab", tabID => {
      this.currentTab = tabID;
    });
    // A global signal listener to increment tab
    this.$emitter.on("globalIncrementTab", () => {
      this.incrementTabBy(1);
    });
    // A global signal listener to decrement tab
    this.$emitter.on("globalDecrementTab", () => {
      this.incrementTabBy(-1);
    });
  },

  beforeUnmount() {
    // Then we call that function here to unwatch
    if (this.unwatchStoreFunction) {
      this.unwatchStoreFunction();
      this.unwatchStoreFunction = null;
    }
  },

  methods: {
    updatePlugins: function() {
      return axios
        .get(this.pluginsUri)
        .then(response => {
          this.plugins = response.data;
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },
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
      this.$refs["calibrationModal"].show();
    },
    enterApp: function() {
      // Stuff to do once connected and all init modals are finished
    }
  }
};
</script>

<style scoped lang="less">
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
