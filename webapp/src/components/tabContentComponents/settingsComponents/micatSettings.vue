<template>
  <div v-observe-visibility="visibilityChanged" id="micatSettings">
    <div>
      This will estimate your pixel size from a USAF 1951 calibration
      slide. Position the smallest resolvable element towards the
      centre of the field of view. <br>
      Set the group and element to the smallest that is being detected
      by PREVIEW. If dirt or anything else on the sample is being
      labelled as a group of lines, you'll need to clean it or move
      away - our program currently can't filter them out.
      <br>
      <br>
    </div>
    <div class="uk-grid uk-grid-divider uk-child-width-expand" uk-grid>
      <div class="uk-width-1-4@m">
        
      <!-- Grid managing tab content -->
          <action-button
          thing="micat"
          action="generate_preview"
          submit-label="Preview micat results"
          class="uk-margin"
          :requires-confirmation="false"
          :poll-interval="0.1"
          :submit-data="{group : group, element: element}"
          @response="updatePreview()"
          />
          <action-button
          thing="micat"
          action="run_micat"
          submit-label="Run micat analysis"
          class="uk-margin"
          :requires-confirmation="false"
          :modal-progress="true"
          :poll-interval="0.1"
          :submit-data="{group : group, element: element}"
          @response="updatePreview()"
          />
        <label class="uk-form-label" for="form-stacked-text">Group</label>
        <div class="uk-form-controls">
        <input
          v-model="group"
          class="uk-input uk-form-small"
          type="number"
          name="group"
        />
      </div>
      <label class="uk-form-label" for="form-stacked-text">Element</label>
        <div class="uk-form-controls">
        <input
          v-model="element"
          class="uk-input uk-form-small"
          type="number"
          name="element"
        />
      </div>
      <p> The physical size of a pixel is {{ um_per_px }} microns <br>
        The uncertainty of that size is {{ um_per_px_uncert }} microns <br>
        FOV is {{ fov }} microns <br>
        Uncertainty on FOV is {{ fov_uncert }} microns <br>
        Based on an image / stream size of {{ image_size }} <br>
        </p>
        </div>
        <div class="uk-grid uk-child-width-expand uk-height-match" uk-grid>
        <div>
          <miniStreamDisplay />
        </div>
        <div>
      <img
        v-if="displayImageOnRight"
        id="last-stitched-image"
        :src="lastStitchedImage"
        @error="$(this).hide();"
      />
    </div>
      </div>
    </div>
  </div>
</template>
    
    <script>
    import miniStreamDisplay from "../../genericComponents/miniStreamDisplay.vue"
    import ActionButton from "../../labThingsComponents/actionButton.vue";
    
    export default {
      name: "micatSettings",
    
      components: {
        miniStreamDisplay,
        ActionButton
      },
    
      data: function() {
        return {
            lastStitchedImage: null,
            group: 7,
            element: 6,
            dataStr: null,
            fov: null,
            fov_uncert: null,
            um_per_px: null,
            um_per_px_uncert: null,
            image_size: null
        };
      },
    
      computed: {
        displayImageOnRight() {
            return this.lastStitchedImage !== null;
        }
      },

      methods:{
        visibilityChanged(isVisible) {
        if (isVisible) {
            this.updatePreview();
            this.getMicatData();
            }
        },
        async updatePreview() {
            let currentTime = Date.now()
            this.lastStitchedImage = `${this.$store.getters.baseUri}/micat/get_latest_preview.png?t=${currentTime}`;
            this.getMicatData();
        },
        async getMicatData() {
          let data = await this.readThingProperty(
          "micat",
          "last_micat"
          );
          if (data == {}) {
            throw "No calibration data available.";
          }
          let dataDict = JSON.parse(JSON.stringify(data))
          this.fov = [
            Number(dataDict["field_of_view"][0].toFixed(0)),
            Number(dataDict["field_of_view"][1].toFixed(0))
          ];
          this.fov_uncert = [
            Number(dataDict["field_of_view_uncert"][0].toFixed(2)),
            Number(dataDict["field_of_view_uncert"][1].toFixed(2))
          ];
          this.um_per_px = Number(dataDict["um_per_px"].toFixed(3));
          this.um_per_px_uncert = Number(dataDict["um_per_px_uncert"].toFixed(6));
          this.image_size = dataDict["fov_pixels"][0]
          }
      }
    };
    </script>
    