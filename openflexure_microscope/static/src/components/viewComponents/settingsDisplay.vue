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
        <li>
          <tabIcon
            id="settings-microscope-icon"
            tab-i-d="microscope"
            :show-title="false"
            :show-tooltip="false"
            :require-connection="true"
            :current-tab="currentTab"
            @set-tab="setTab"
          >
            General
          </tabIcon>
        </li>
      </ul>
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
        tab-i-d="camera"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <cameraSettings />
        </div>
      </tabContent>

      <tabContent
        tab-i-d="mapping"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <h3>Camera/stage mapping</h3>
          <p>
            Camera/stage mapping allows the stage to move relative to the camera
            view. This enables functions like click-to-move, and more precise
            tile scans.
          </p>
          <cameraStageMappingSettings />
        </div>
      </tabContent>

      <tabContent
        tab-i-d="microscope"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <h3>Microscope settings</h3>
          <microscopeSettings />
        </div>
      </tabContent>
    </div>
  </div>
</template>

<script>
import streamSettings from "./settingsComponents/streamSettings.vue";
import microscopeSettings from "./settingsComponents/microscopeSettings.vue";
import cameraSettings from "./settingsComponents/cameraSettings.vue";
import appSettings from "./settingsComponents/appSettings.vue";
import cameraStageMappingSettings from "./settingsComponents/cameraStageMappingSettings.vue";

// Import generic components
import tabIcon from "../genericComponents/tabIcon";
import tabContent from "../genericComponents/tabContent";

// Export main app
export default {
  name: "SettingsDisplay",

  components: {
    streamSettings,
    cameraSettings,
    microscopeSettings,
    cameraStageMappingSettings,
    appSettings,
    tabIcon,
    tabContent
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

<style lang="less">
.settings-pane {
  border-width: 0 1px 0 0;
  border-style: solid;
  border-color: rgba(180, 180, 180, 0.25);
}

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
</style>
