import { doFetch } from "./utils.js";

class StateManager {
    viewer;
    background_save_interval;
    current_state;
    changed;
    just_loaded;
    
    constructor( viewer ) {
        this.viewer = viewer;
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
        state.cameras.map((c,n)=> {
            this.viewer.viewports[n].setCamera(c);
        })
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
        this.current_state = state;
    }
    async save() {
        if (!this.viewer.case_id) return;
        console.info("Saving state.")
        const state = this._calcState()
        if (state) {
            await doFetch(`/api/case/${this.viewer.case_id}/session`, state)
            // localStorage.setItem(this.viewer.case_id, JSON.stringify(state));
            this.current_state = state;
            this.changed = false;
        }
    }
    async load() {
        if (!this.viewer.case_id) return;
        var state;
        // var state = JSON.parse(localStorage.getItem(this.viewer.case_id));
        state = await doFetch(`/api/case/${this.viewer.case_id}/session`,{},"GET")
        if (!state) {
            return;
        }
        console.info("Loading state");
        this._applyState(state);
        this.viewer.renderingEngine.renderViewports(this.viewer.viewportIds);
        this.changed = false;
        this.just_loaded = true;
    }

    startBackgroundSave(){ 
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

    stopBackgroundSave(){
        if (this.background_save_interval) {
            clearInterval(this.background_save_interval);
        }
    }

    setChanged() {
        this.changed = true;
    }
}

export { StateManager }