<template>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <div class="settings-nav">
      <ul class="uk-nav uk-nav-default">
        <li class="uk-nav-header">Application settings</li>
        <li>
          <tabIcon
            id="settings-display-icon"
            tab-i-d="display"
            :show-title="false"
            :show-tooltip="false"
            :require-connection="false"
            :current-tab="currentTab"
            @set-tab="setTab"
          >
            Display
          </tabIcon>
        </li>
        <li>
          <tabIcon
            id="settings-features-icon"
            tab-i-d="features"
            :show-title="false"
            :show-tooltip="false"
            :require-connection="false"
            :current-tab="currentTab"
            @set-tab="setTab"
          >
            Features
          </tabIcon>
        </li>
        <li class="uk-nav-header">Microscope settings</li>
        <li>
          <tabIcon
            id="settings-camera-icon"
            tab-i-d="camera"
            :show-title="false"
            :show-tooltip="false"
            :require-connection="true"
            :current-tab="currentTab"
            @set-tab="setTab"
          >
            Camera
          </tabIcon>
        </li>
        <li>
          <tabIcon
            id="settings-camera-icon"
            tab-i-d="micat"
            :show-title="false"
            :show-tooltip="false"
            :require-connection="true"
            :current-tab="currentTab"
            @set-tab="setTab"
          >
            micat
          </tabIcon>
        </li>
        <li>
          <tabIcon
            id="settings-stage-icon"
            tab-i-d="stage"
            :show-title="false"
            :show-tooltip="false"
            :require-connection="true"
            :current-tab="currentTab"
            @set-tab="setTab"
          >
            Stage
          </tabIcon>
        </li>
        <li>
          <tabIcon
            id="settings-mapping-icon"
            tab-i-d="mapping"
            :show-title="false"
            :show-tooltip="false"
            :require-connection="true"
            :current-tab="currentTab"
            @set-tab="setTab"
          >
            Camera/stage mapping
          </tabIcon>
        </li>
      </ul>
      <action-button
        thing="settings"
        action="save_all_thing_settings"
        submit-label="Save all settings"
        class="uk-margin"
      />
    </div>
    <div class="view-component uk-width-expand uk-padding-small">
      <tabContent
        tab-i-d="display"
        :require-connection="false"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <appSettings />
          <streamSettings />
        </div>
      </tabContent>

      <tabContent
        tab-i-d="features"
        :require-connection="false"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <featuresSettings />
        </div>
      </tabContent>

      <tabContent
        tab-i-d="micat"
        :require-connection="false"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <micatSettings />
        </div>
      </tabContent>

      <tabContent
        tab-i-d="camera"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <cameraSettings />
        </div>
      </tabContent>

      <tabContent
        tab-i-d="stage"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <stageSettings />
        </div>
      </tabContent>

      <tabContent
        tab-i-d="mapping"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <CSMSettings />
        </div>
      </tabContent>
    </div>
  </div>
</template>

<script>
import streamSettings from "./settingsComponents/streamSettings.vue";
import cameraSettings from "./settingsComponents/cameraSettings.vue";
import appSettings from "./settingsComponents/appSettings.vue";
import featuresSettings from "./settingsComponents/featuresSettings.vue";
import CSMSettings from "./settingsComponents/CSMSettings.vue";
import stageSettings from "./settingsComponents/stageSettings.vue";
import micatSettings from "./settingsComponents/micatSettings.vue";
// Import generic components
import tabIcon from "../genericComponents/tabIcon";
import tabContent from "../genericComponents/tabContent";
import ActionButton from "../labThingsComponents/actionButton.vue";

// Export main app
export default {
  name: "SettingsContent",

  components: {
    streamSettings,
    cameraSettings,
    stageSettings,
    CSMSettings,
    micatSettings,
    appSettings,
    featuresSettings,
    tabIcon,
    tabContent,
    ActionButton
  },

  data: function() {
    return {
      selected: "display",
      currentTab: "display"
    };
  },

  methods: {
    setTab: function(event, tab) {
      if (!(this.currentTab == tab)) {
        this.currentTab = tab;
      }
    }
  }
};
</script>

<style lang="less" scoped>
// Custom UIkit CSS modifications
@import "../../assets/less/theme.less";

.settings-nav {
  overflow-y: auto;
  overflow-x: hidden;
  width: 250px;
  padding: 10px;
  background-color: rgba(180, 180, 180, 0.03);
  border-width: 0 1px 0 0;
  border-style: solid;
  border-color: rgba(180, 180, 180, 0.25);
}

.settings-nav li > a {
  padding-left: 6px !important;
  border-radius: @button-border-radius;
}
</style>
