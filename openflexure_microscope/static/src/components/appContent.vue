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
    <div
      id="switcher-left"
      class="uk-flex uk-flex-column uk-padding-remove uk-width-auto uk-height-1-1 uk-text-center"
    >
      <tabIcon
        id="view-tab-icon"
        tab-i-d="view"
        :require-connection="true"
        :current-tab="currentTab"
        @set-tab="setTab"
      >
        <i class="material-icons">visibility</i>
      </tabIcon>

      <tabIcon
        id="gallery-tab-icon"
        tab-i-d="gallery"
        :require-connection="true"
        :current-tab="currentTab"
        @set-tab="setTab"
      >
        <i class="material-icons">photo_library</i>
      </tabIcon>

      <hr />

      <tabIcon
        id="navigate-tab-icon"
        tab-i-d="navigate"
        :require-connection="true"
        :current-tab="currentTab"
        @set-tab="setTab"
      >
        <i class="material-icons">gamepad</i>
      </tabIcon>
      <tabIcon
        id="capture-tab-icon"
        tab-i-d="capture"
        :require-connection="true"
        :current-tab="currentTab"
        @set-tab="setTab"
      >
        <i class="material-icons">camera_alt</i>
      </tabIcon>
      <tabIcon
        id="settings-tab-icon"
        tab-i-d="settings"
        :require-connection="false"
        :current-tab="currentTab"
        @set-tab="setTab"
      >
        <i class="material-icons">settings</i>
      </tabIcon>

      <hr id="extension-tab-divider" />

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

      <tabIcon
        id="about-tab-icon"
        class="uk-margin-auto-top"
        tab-i-d="about"
        :require-connection="false"
        :current-tab="currentTab"
        @set-tab="setTab"
      >
        <i class="material-icons">info</i>
      </tabIcon>
    </div>

    <!-- Corresponding vertical tab content -->
    <div
      id="container-left"
      class="uk-padding-remove uk-height-1-1 uk-width-expand"
    >
      <tabContent
        tab-i-d="view"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <viewContent />
      </tabContent>
      <tabContent
        tab-i-d="gallery"
        :require-connection="false"
        :current-tab="currentTab"
      >
        <galleryContent />
      </tabContent>
      <tabContent
        tab-i-d="navigate"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <navigateContent />
      </tabContent>
      <tabContent
        tab-i-d="capture"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <captureContent />
      </tabContent>
      <tabContent
        tab-i-d="settings"
        :require-connection="false"
        :current-tab="currentTab"
      >
        <settingsContent class="section-content" />
      </tabContent>

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

      <tabContent
        tab-i-d="about"
        :require-connection="false"
        :current-tab="currentTab"
      >
        <aboutContent class="section-content" />
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
import viewContent from "./tabContentComponents/viewContent.vue";
import settingsContent from "./tabContentComponents/settingsContent.vue";
import galleryContent from "./tabContentComponents/galleryContent.vue";
import extensionContent from "./tabContentComponents/extensionContent.vue";
import aboutContent from "./tabContentComponents/aboutContent.vue";

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
    viewContent,
    settingsContent,
    galleryContent,
    extensionContent,
    calibrationModal,
    aboutContent
  },

  data: function() {
    return {
      plugins: [],
      currentTab: "view",
      unwatchStoreFunction: null
    };
  },

  computed: {
    pluginsUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/extensions`;
    },
    pluginsGuiList: function() {
      // List of plugin GUIs, obtained from this.plugins values
      console.log("Recalculating plugins");
      var pluginGuis = [];
      for (let plugin of Object.values(this.plugins)) {
        if (plugin.meta.gui) {
          pluginGuis.push(plugin.meta.gui);
        }
      }
      return pluginGuis;
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
        this.$store.commit("changeSetting", ["disableStream", true]);
        this.$store.commit("changeSetting", ["autoGpuPreview", true]);
        this.$store.commit("changeSetting", ["trackWindow", true]);
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
    this.$root.$on("globalSwitchTab", tabID => {
      this.currentTab = tabID;
    });
  },

  beforeDestroy() {
    // Then we call that function here to unwatch
    if (this.unwatchStoreFunction) {
      this.unwatchStoreFunction();
      this.unwatchStoreFunction = null;
    }
  },

  methods: {
    updatePlugins: function() {
      console.log("Updating plugin forms");
      return axios
        .get(this.pluginsUri)
        .then(response => {
          console.log(response);
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
    startModals: function() {
      this.$refs["calibrationModal"].show();
    },
    enterApp: function() {
      // Stuff to do once connected and all init modals are finished
      console.log("Entering main application");
      this.currentTab = "view";
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
  overflow: hidden;
  background-color: rgba(180, 180, 180, 0.025);
  width: 100%;
  height: 100%;
}

#switcher-left {
  border-width: 0 1px 0 0;
  border-style: solid;
  border-color: rgba(180, 180, 180, 0.25);
}

#switcher-left a {
  padding: 10px 8px;
}

#switcher-left {
  width: 75px;
  background-color: rgba(180, 180, 180, 0.1);
  padding-top: 2px !important;
}
</style>
