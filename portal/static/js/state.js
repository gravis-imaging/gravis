class StateManager {
    viewer;
    background_save_interval;

    constructor( viewer ) {
        this.viewer = viewer;
    }

    _calcState() {
        if (!this.viewer.viewports[0].getDefaultActor()) {
            return;
        }
        const cameras = this.viewer.viewports.map(v=>v.getCamera());
        const voi = this.viewer.getVolumeVOI(this.viewer.viewports[0]);
        const annotations = this.viewer.annotation_manager.getAllAnnotations();
        for (let a of annotations) {
            a.data.cachedStats = {}
        }
        return { cameras, voi, annotations };
    }
    save() {
        if (!this.viewer.case_id) return;
        console.info("Saving state.")
        const state = this._calcState()
        if (state)
            localStorage.setItem(this.viewer.dicom_set, JSON.stringify(state));
    }
    load() {
        var state = JSON.parse(localStorage.getItem(this.viewer.dicom_set));
        if (!state) {
            return;
        }
        console.info("Loading state");
        state.cameras.map((c,n)=> {
            this.viewer.viewports[n].setCamera(c);
        })
        if ( state.voi ) {
            const [ lower, upper ] = state.voi;
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
        this.viewer.renderingEngine.renderViewports(this.viewer.viewportIds);
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
}

export { StateManager }