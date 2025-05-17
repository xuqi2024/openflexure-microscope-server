<template>
    <div id="calibrationSuite">
        <div class="uk-grid uk-grid-divider uk-child-width-expand" uk-grid>
            <div class="uk-width-large">
                <h3>Calibration Suite</h3>
                <action-button
                thing="range_of_motion"
                action="measure_rom"
                submit-label="Measure range of motion"
                :can-terminate="true"
                :requires-confirmation="true"
                :modal-progress="true"
                :confirmation-message="
                'The stage will now move, measuring the stage range of motion. This requires a sample to be visible '
                + 'in the microscope big enough to cover the full range of motion, and the stage to be roughly centred. OK to proceed?'
                "
                :poll-interval="0.1"
                />
            </div>
        </div>
    </div>
</template>