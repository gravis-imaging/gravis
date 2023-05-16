import { confirmPrompt, doFetch, errorPrompt, fixUpCrosshairs } from "./utils.js";

class StateManager {
    viewer;
    background_save_interval;
    current_state;
    changed;
    ignore_changed;
    just_loaded;
    session_id;
    session_list = [];

    constructor( viewer ) {
        this.viewer = viewer;
        this.ignore_changed=false;
    }

    _calcAnnotations() {
        const annotations = this.viewer.annotation_manager.getAllAnnotations();
        for (let a of annotations) {
            a.data.cachedStats = {}
        }
        return annotations;
    }

    _calcState() {
        if (!this.viewer.viewports[0].getDefaultActor()) {
            return;
        }
        const cameras = this.viewer.viewports.map(v=>v.getCamera());
        const dicom_set_voi = this.viewer.getVolumeVOI(this.viewer.viewports[0]);
        const annotations = this._calcAnnotations();

        var voi = {[this.viewer.dicom_set]: dicom_set_voi};
        if ( this.current_state && this.current_state.voi ) {
            voi = { ...this.current_state.voi, [this.viewer.dicom_set]: dicom_set_voi}
        } 
        return { cameras, voi, annotations };
    }

    _applyState(state) {
        state.cameras.slice(0,3).map((c,n)=> {
            this.viewer.viewports[n].setCamera(c);
        })
        // TODO fix this workaround. If I set the aux camera with the others, it ends up zooming all the way out for some reason.
        // this does not work if the first aux dicomset is not a volume. 
        if (state.cameras.length > 3) {
            const fixAuxViewport = (evt) => {
                // Wait for the aux volume to load
                if (evt.detail.volume.volumeId.endsWith("_AUXVOLUME")) {
                    // Wait for the next frame...
                    window.requestAnimationFrame( () => {
                        // Set the camera...
                        this.viewer.viewports[3].setCamera(state.cameras[3]);
                        this.viewer.viewports[3].render();
                    });
                    cornerstone.eventTarget.removeEventListener("CORNERSTONE_VOLUME_LOADED", fixAuxViewport);
                    // cornerstone.eventTarget.removeEventListener("CORNERSTONE_STACK_VIEWPORT_NEW_STACK", fixAuxViewportStack);
                };
            }
            // this doesn't reliably work
            // const fixAuxViewportStack = (evt) => {
            //     if (evt.detail.viewportId = "VIEW_AUX" ) {
            //         window.setTimeout( () => {
            //             // Set the camera...
            //             this.viewer.viewports[3].setCamera(state.cameras[3]);
            //             this.viewer.viewports[3].render();
            //         },5000);
            //         cornerstone.eventTarget.removeEventListener("CORNERSTONE_VOLUME_LOADED", fixAuxViewport);
            //         cornerstone.eventTarget.removeEventListener("CORNERSTONE_STACK_VIEWPORT_NEW_STACK", fixAuxViewportStack);
            //     }
            // }
            cornerstone.eventTarget.addEventListener("CORNERSTONE_VOLUME_LOADED", fixAuxViewport);
            // cornerstone.eventTarget.addEventListener("CORNERSTONE_STACK_VIEWPORT_NEW_STACK", fixAuxViewportStack);
        }
        fixUpCrosshairs();
        if ( state.voi && state.voi[this.viewer.dicom_set]) {
            const [ lower, upper ] = state.voi[this.viewer.dicom_set];
            this.viewer.viewports[0].setProperties( { voiRange: {lower,upper}})
        }
        if ( state.annotations ) {
            const annotationState = cornerstone.tools.annotation.state;
            let old_annotations = []
            for (let v of this.viewer.viewports.slice(0,3)) {
                old_annotations = this.viewer.annotation_manager.getAllAnnotations(v);
                if (!old_annotations) continue;
                for (let a of old_annotations) {
                    annotationState.removeAnnotation(a.annotationUID, v.element)
                }
            }
            for (var a of Object.keys(this.viewer.annotation_manager.annotations)) {
                delete this.viewer.annotation_manager.annotations[a];
            }
            for (var a of state.annotations) {
                this.viewer.annotation_manager.annotations[a.annotationUID] = { uid: a.annotationUID, label: a.data.label, ...a.metadata }
                annotationState.addAnnotation(this.viewer.viewports[0].element,a)
            }
        }
        this.current_state = JSON.parse(JSON.stringify(state)); // deep copy for safekeeping
        this.viewer.annotation_manager.updateChart();
    }

    async save() {
        if (!this.viewer.case_id) return;
        console.info("Saving state.")
        const state = this._calcState()
        if (!state) return;
        try {
            await doFetch(`/api/case/${this.viewer.case_id}/session/${this.session_id}`, state)
            // localStorage.setItem(this.viewer.case_id, JSON.stringify(state));
            this.current_state = JSON.parse(JSON.stringify(state)); // deep copy for safekeeping
            this.changed = false;
            return true;
        } catch (e) {
            console.error(e);
            await errorPrompt("Failed to save session.");
            return false;
        }
    }

    async load() {
        if (!this.viewer.case_id) return;
        var state;
        // var state = JSON.parse(localStorage.getItem(this.viewer.case_id));
        if (this.session_id) {
            state = await doFetch(`/api/case/${this.viewer.case_id}/session/${this.session_id}`,{},"GET")
        } else {
            state = await doFetch(`/api/case/${this.viewer.case_id}/session`,{},"GET")
        }
        if (!state) {
            return;
        }
        state = await doFetch(`/api/case/${this.viewer.case_id}/session`,{},"GET")
        this.session_list = (await doFetch(`/api/case/${this.viewer.case_id}/sessions`,{},"GET")).sessions

        console.info("Loading state");
        this._applyState(state);
        this.viewer.renderingEngine.renderViewports(this.viewer.viewportIds);
        this.changed = false;
        this.just_loaded = true;
        this.session_id = state.session_id;
    }

    async switchSession(id) {
        if (this.getChanged()) {
            const result = await confirmPrompt("Discard changes and switch session?", "Unsaved changes detected")
            if (!result.isConfirmed) {
                return;
            }
        }
        try {
            const state = await doFetch(`/api/case/${this.viewer.case_id}/session/${id}`,{},"GET")
            // this.session_list = (await doFetch(`/api/case/${this.viewer.case_id}/sessions`,{},"GET")).sessions
            this.viewer.viewports.map(v=>v.resetCamera());
            this._applyState(state)
            this.viewer.renderingEngine.renderViewports(this.viewer.viewportIds);
            this.changed = false;
            this.just_loaded = true;
            this.session_id = state.session_id;
        } catch (e) {
            console.error(e);
            await errorPrompt("Failed to switch session.");
        }
    }

    async newSession() {
        try {
            const state = await doFetch(`/api/case/${this.viewer.case_id}/session/new`,{},"POST")
        } catch (e) {
            console.error(e);
            await errorPrompt("Failed to create session.");
            return;
        }
        this.session_list = (await doFetch(`/api/case/${this.viewer.case_id}/sessions`,{},"GET")).sessions
        this._applyState(state)
        this.viewer.renderingEngine.renderViewports(this.viewer.viewportIds);
        this.changed = false;
        this.just_loaded = true;
        this.session_id = state.session_id;
    }

    startBackgroundSave() { 
        if (this.background_save_interval) {
            return;
        }
        const saveStateSoon = () => {
            requestIdleCallback(this.save.bind(this));
        }
        document.addEventListener('visibilitychange', ((event) => { 
            if (document.visibilityState === 'hidden') {
                this.save();
            } else if (document.visibilityState === 'visible') {
                this.save();
            }
        }).bind(this));
        this.background_save_interval = setInterval(saveStateSoon.bind(this), 1000);
    }

    stopBackgroundSave() {
        if (this.background_save_interval) {
            clearInterval(this.background_save_interval);
        }
    }

    setChanged(reason) {
        this.changed = true;
        if (reason) {
            console.log("Changed:", reason)
        }
        return true;
    }

    setIgnoreChanged() {
        this.ignore_changed=true;
    }

    getChanged() {
        if (this.ignore_changed) {
            return false;
        }
        if (this.changed) {
            return true;
        }
        if (!this.current_state) {
            return false;
        }
        const loaded_annotations = this.current_state.annotations;
        const annotations = this._calcAnnotations();

        // Number of annotations differs
        if (annotations.length != loaded_annotations.length) {
            return this.setChanged("number of annotations differs");
        }
        const loaded_annotations_dict = {}
        for (const a of loaded_annotations) {
            loaded_annotations_dict[a.annotationUID] = a;
        }

        for ( const a of annotations) {
            const old_version = loaded_annotations_dict[a.annotationUID]
            if (!old_version) return this.setChanged("new annotation");
            const old_data = old_version.data;
            if (JSON.stringify(old_data.handles.points) !== JSON.stringify(a.data.handles.points)) return this.setChanged("points");
            if (old_data.label != a.data.label) return this.setChanged("label");
            
            for (var i=0;i<3;i++) {
                if (Math.abs(old_data.handles.textBox.worldPosition[i] - a.data.handles.textBox.worldPosition[i]) > 0.000001) {
                    console.log(JSON.stringify(old_data.handles.textBox.worldPosition),JSON.stringify(a.data.handles.textBox.worldPosition));
                    return this.setChanged("textbox");
                }
            }
        }
        return false;
    }
}

export { StateManager }
