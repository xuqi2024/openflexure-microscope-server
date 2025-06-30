<template>
  <!-- Grid managing tab content -->
  <div uk-grid class="uk-height-1-1 uk-margin-remove uk-padding-remove">
    <calibrationModal
      ref="calibrationModal"
      @onClose="enterApp()"
    ></calibrationModal>
    <div class="settings-nav">
      <ul class="uk-nav uk-nav-default">
        <li class="uk-nav-header">Application Settings</li>
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
        <li class="uk-nav-header">Microscope Settings</li>
        <button
        submit-label="Launch Calibration Wizard"
        type="button"
        class="uk-button uk-button-default uk-width-1-1"
        @click="startModals"
        >Launch Calibration Wizard</button>
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
            Camera Calibration
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
            Camera to Stage Mapping
          </tabIcon>
        </li>
        <li>
          <tabIcon
            id="settings-stage-icon"
            tab-i-d="range-of-motion"
            :show-title="false"
            :show-tooltip="false"
            :require-connection="true"
            :current-tab="currentTab"
            @set-tab="setTab"
          >
            Range of Motion
          </tabIcon>
        </li>
      </ul>
      <action-button
        thing="range_of_motion"
        action="calibration_data_generate"
        submit-label="Generate Calibration Data"
        @response="alertPDF"
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
        tab-i-d="camera"
        :require-connection="true"
        :current-tab="currentTab"
      >
        <div class="settings-pane uk-padding-small">
          <cameraSettings />
        </div>
      </tabContent>

      <tabContent
        tab-i-d="range-of-motion"
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
import calibrationModal from "../modalComponents/calibrationModal.vue";
import cameraSettings from "./settingsComponents/cameraSettings.vue";
import appSettings from "./settingsComponents/appSettings.vue";
import CSMSettings from "./settingsComponents/CSMSettings.vue";
import stageSettings from "./settingsComponents/stageSettings.vue";
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
    appSettings,
    tabIcon,
    tabContent,
    ActionButton,
    calibrationModal
  },

  data: function() {
    return {
      selected: "display",
      currentTab: "display",
    };
  },

  methods: {
    setTab: function(event, tab) {
      if (!(this.currentTab == tab)) {
        this.currentTab = tab;
      }
    },
    startModals: function() {
      this.$refs.calibrationModal.force_show();
    },
    alertPDF(response) {
      const href = response.output.href
      if (href) {
        this.create_download(href);
      } else {
        console.error("No PDF href found in response:", response);
      }
      this.modalNotify(`PDF has been created and downloaded.`);
    },
    async create_download(pdfUrl) {
      try {
        const urlWithCacheBuster = `${pdfUrl}?t=${Date.now()}`;

        const response = await fetch(urlWithCacheBuster, { cache: "no-store" });

        const blob = await response.blob();
        const bloburl = URL.createObjectURL(blob);


        const a = document.createElement("a");
        a.href = bloburl;
        a.download = "calibration_summary.pdf"; // you can change this filename
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(bloburl); // clean up the object URL
      } catch (err) {
        console.error("Download failed:", err);
      }
    }
    }
  }
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
