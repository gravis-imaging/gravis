import { doFetch, HSLToRGB, Vector, scrollViewportToPoint, confirmPrompt, errorToast, inputPrompt, download } from "./utils.js"

class AnnotationManager {
    viewer;
    annotations = {};
    aux_stats = [];
    current_annotation_tool = null;
    constructor( viewer ) {
        this.viewer = viewer;

        cornerstone.eventTarget.addEventListener("CORNERSTONE_TOOLS_ANNOTATION_ADDED",(evt) => {
            if (evt.detail.annotation.annotationUID in this.annotations) {
                return;
            }
            if (["EllipticalROI", "Probe"].indexOf(evt.detail.annotation.metadata.toolName) == -1) {
                return;
            }
            var idx = Math.max(0,...Object.values(this.annotations).map(a => a.idx+1));
            const new_annotation = cornerstone.tools.annotation.state.getAnnotation(evt.detail.annotation.annotationUID)
            new_annotation.chartColor = `rgb(${HSLToRGB(idx*(360/1.618033988),50,50).join(",")})`;
            new_annotation.metadata.idx = idx;
            new_annotation.metadata.viewportId = evt.detail.viewportId;
            new_annotation.data.label = `${{"EllipticalROI":"ROI","Probe":"Probe"}[new_annotation.metadata.toolName]} ${idx+1}`;
            this.annotations[new_annotation.annotationUID] = { uid: new_annotation.annotationUID, label: new_annotation.data.label, ...new_annotation.metadata }

            let e = new CustomEvent("annotations-update", {
                detail: {}
              });
              window.dispatchEvent(e);
        }
    )
    }

    getAllAnnotations(viewport) {
        return ["EllipticalROI","Probe"].flatMap(
            type => cornerstone.tools.annotation.state.getAnnotations(type,(viewport || this.viewer.viewports[0]).element) || []
        );
    }
      
    exportChart(acc) {
        const name = ["gravis",
                        acc,
                        this.viewer.chart_options['adjust'],
                        this.viewer.chart_options['mode'],
                        new Date().toLocaleString('sv').replace(' ','T').replaceAll(':','')
                    ].join("_")

        const table = [this.viewer.chart.getLabels().map(x=>`"${x}"`), ...this.viewer.chart.file_];
        const csv = table.map(x=>x.join(",")).join("\r\n");
        
        const file = new File([csv], `${name}.csv`, {
            type: 'text/csv',
        });
        successToast("Export initiated.");
        download(file);
    }

    exportAuxStats(acc) {
        const name = ["gravis",
                        acc,
                        this.viewer.case_data.case_type,
                        "stats",
                        new Date().toLocaleString('sv').replace(' ','T').replaceAll(':','')
                    ].join("_")
        const stats = this.viewer.aux_manager.current_stats
        let rois = Object.keys(stats);
        let columns = Object.keys(stats[rois[0]])
        let table = [["",...columns]]
        for (let roi of rois) {
            let row = [roi,]
            for (let column of columns) {
                row.push(stats[roi][column])
            }
            table.push(row)
        }
        const csv = table.map(x=>x.join(",")).join("\r\n");
        const file = new File([csv], `${name}.csv`, {
            type: 'text/csv',
        });
        successToast("Export initiated.");
        download(file);
    }
    getAnnotationsQuery(annotations) {
        var labels = ["time",]
        var data = []
        var seriesOptions = {}

        for (var annotation of annotations){
            let handles_indexes = annotation.data.handles.points.map( pt=>cornerstone.utilities.transformWorldToIndex(this.viewer.volume.imageData, pt))
            let out_of_bounds = false;
            for (let h of handles_indexes) {
                if (! cornerstone.utilities.indexWithinDimensions(h, this.viewer.volume.dimensions)) {
                    out_of_bounds = true;
                }
            }
            if (out_of_bounds) {
                continue
            }
            data.push( {
                normal: annotation.metadata.viewPlaneNormal,
                view_up: annotation.metadata.viewUp,
                bounds: this.viewer.volume.imageData.getBounds(),
                handles: annotation.data.handles.points,
                handles_indexes: handles_indexes,
                tool: annotation.metadata.toolName,
                label: annotation.data.label
            })
            labels.push(annotation.data.label)
            seriesOptions[annotation.data.label] = { color: annotation.chartColor }
        }
        return { data, labels, seriesOptions }
    }
    async updateChart() {
        if (!this.viewer.volume || !this.viewer.volume.imageData ) {
            return;
        }
        let annotations = this.getAllAnnotations();
        if (! annotations ) {
            if (this.viewer.chart.file_.length > 0 )
                this.viewer.chart.updateOptions( {file: [] });
            return;
        }
        // if (this.viewer.aux_manager.getStats) {
        //     let event = new CustomEvent("stats-update", {
        //         detail: {
        //           items: this.viewer.aux_manager.getStats()
        //         }
        //       });
        //       window.dispatchEvent(event);
        // }
        let { data, labels, seriesOptions } = this.getAnnotationsQuery(annotations);
        try {
            const timeseries = await doFetch(`/api/case/${this.viewer.case_id}/dicom_set/${this.viewer.dicom_set}/timeseries`, {annotations: data, chart_options: this.viewer.chart_options})
            const options = { 'file':  timeseries["data"], labels: labels, series: seriesOptions} 
            this.viewer.chart.updateOptions( options );
        } catch (e) {
            console.warn(e)
            return
        }
    }

    createAnnotationTemplate(tool_name) {
        var idx = Math.max(0,...Object.values(this.annotations).map(a => a.idx+1));
        let tool_name_label = "Probe";
        if (tool_name == "EllipticalROI") {
            tool_name_label = "ROI";
        }
        return {
            chartColor: `rgb(${HSLToRGB(idx*(360/1.618033988),50,50).join(",")})`,
            highlighted: true,
            invalidated: false,
            isLocked: false,
            isVisible: true,
            annotationUID: cornerstone.utilities.uuidv4(),
            metadata: {
                idx: idx,
            },
            data: {
                cachedStats: {},
                label: `${tool_name_label} ${idx+1}`,
                handles: {
                    textBox:{"hasMoved":false,"worldPosition":[0,0,0],"worldBoundingBox":{"topLeft":[0,0,0],"topRight":[0,0,0],"bottomLeft":[0,0,0],"bottomRight":[0,0,0]}},
                    activeHandleIndex: null
                },
            }
        }
    }

    duplicateSelectedAnnotation() {
        for (let a of this.getSelectedFilteredAnnotations() ) {
            if (!a) { continue }

            let new_a = this.createAnnotationTemplate(a.metadata.toolName);
            new_a.metadata = { ...a.metadata, idx: new_a.metadata.idx };
            new_a.data.handles.points = a.data.handles.points.slice().map(p=>p.slice());
            const viewport = this.viewer.viewports.find(x => x.id == new_a.metadata.viewportId);
            cornerstone.tools.annotation.state.addAnnotation(new_a,viewport.element)
            cornerstone.tools.annotation.selection.setAnnotationSelected(a.annotationUID, false, true);
            cornerstone.tools.annotation.selection.setAnnotationSelected(new_a.annotationUID, true, true);

            cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.viewer.renderingEngine,[new_a.metadata.viewportId]) 
            this.annotations[new_a.annotationUID] = { uid: new_a.annotationUID, label: new_a.data.label, ...new_a.metadata }
        }
    }

    async renameAnnotation() {
        const selAnnotations = this.getSelectedFilteredAnnotations();
        if (selAnnotations.length != 1 || (!selAnnotations[0])) {
            errorToast("Select one annotation to rename.");
            return;
        }
        const a = selAnnotations[0];
        const { value: result } = await inputPrompt("Annotation name", "Annotation name", "name", a.data.label);
        if ( result )  {
            a.data.label = result;
        }
        this.annotations[a.annotationUID].label = result;
        cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.viewer.renderingEngine,this.viewer.viewportIds);
    }
    getSelectedFilteredAnnotations() {
        let annotation_uids = cornerstone.tools.annotation.selection.getAnnotationsSelected() || []
        let annotations = annotation_uids.map(cornerstone.tools.annotation.state.getAnnotation)
        return annotations.filter(x=> x && ["EllipticalROI", "Probe"].indexOf(x.metadata.toolName)>-1)
    }

    deleteSelectedAnnotations() {
        for (let a of this.getSelectedFilteredAnnotations() ) {
            if (!a) { continue }
            cornerstone.tools.annotation.state.removeAnnotation(a.annotationUID)
            cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.viewer.renderingEngine,[a.metadata.viewportId]) 
            delete this.annotations[a.annotationUID];
        }
        this.updateChart();
        this.viewer.aux_manager.updateAnnotationStats();
    }
    
    async deleteAllAnnotations() {
        const result = await confirmPrompt("Do you really want to delete all annotations?")
        if (!result.isConfirmed) {
            return;
        }
        const annotations = this.getAllAnnotations();
        if ( !annotations ) {
            return;
        }
        for (var a of annotations) {
            if (!a) { continue }
            cornerstone.tools.annotation.state.removeAnnotation(a.annotationUID)
            delete this.annotations[a.annotationUID];
        }
        this.updateChart();
        this.viewer.aux_manager.updateAnnotationStats();
        cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.viewer.renderingEngine,this.viewer.viewportIds)
    }

    flipSelectedAnnotations() {
        let [ left, right ] = this.viewer.volume.imageData.getBounds().slice(0,2);
        let midpoint = (left + right) / 2;
        for (let a of this.getSelectedFilteredAnnotations() ) {
            if (!a) { continue }
            a.data.handles.points.map( point => {
                point[0] = midpoint - (point[0] - midpoint)
            })
            this.goToAnnotation(a.annotationUID);
        }
    }

    setAnnotationTool(tool_name) {
        const Tools = window.cornerstone.tools;
        const Enums = Tools.Enums;
        const toolGroupMain = Tools.ToolGroupManager.getToolGroup(`STACK_TOOL_GROUP_MAIN`);
        const toolGroupAux = Tools.ToolGroupManager.getToolGroup(`STACK_TOOL_GROUP_AUX`);
        const reset = () => [toolGroupAux, toolGroupMain].map(g=>[Tools.EllipticalROITool.toolName, Tools.ProbeTool.toolName].map(x=>g.setToolPassive(x, {
            bindings: [
                {
                    mouseButton: Enums.MouseBindings.Primary,
                },
            ],
        })))
        var groups = [toolGroupMain];
        if (this.viewer.aux_manager.type != "MIP") {
            groups = [toolGroupMain, toolGroupAux];
        }
        reset();
        if (tool_name == this.current_annotation_tool) {
            groups.map(x=>x._setCursorForViewports(x._getCursor()))
            this.current_annotation_tool = null;
            return;
        }

        this.current_annotation_tool = tool_name;
        if (tool_name == "EllipticalROI" ) {
            groups.map(x=>x.setToolActive(Tools.EllipticalROITool.toolName, {
                bindings: [
                    {
                        mouseButton: Enums.MouseBindings.Primary,
                    },
                ],
            }));
        } else if ( tool_name == "Probe") {
            groups.map(x=>x.setToolActive(Tools.ProbeTool.toolName, {
                bindings: [
                    {
                        mouseButton: Enums.MouseBindings.Primary,
                    },
                ],
            }));
        }
    }
    addAnnotationToViewport(tool_name,viewport_n) {
        if (viewport_n == 'aux') {
            var viewport = this.viewer.auxViewport;
        } else {
            var viewport = this.viewer.viewports[viewport_n];
        }
        var cam = viewport.getCamera()
        var center_point = viewport.worldToCanvas(cam.focalPoint)
        if (tool_name == "EllipticalROI" )
            var points = [
                [ center_point[0], center_point[1]-50 ], // top
                [ center_point[0], center_point[1]+50 ], // bottom
                [ center_point[0]-50, center_point[1] ], // left
                [ center_point[0]+50, center_point[1] ], // right
            ].map(viewport.canvasToWorld)
        else if ( tool_name == "Probe") {
            var points = [viewport.canvasToWorld(center_point)];
        } else {
            throw Error(`Unknown annotation type ${tool_name}`)
        }
        let new_annotation = this.createAnnotationTemplate(tool_name);

        if (viewport.type == "stack") {
            new_annotation.metadata.referencedImageId = viewport.getCurrentImageId();
        }
        // "referencedImageId":"wadouri:/media/cases/835a6e6e-5b02-41c2-8e8b-d563f6202a84/processed/dc38895f-b3d3-48a0-ab09-3ebf1202772a/METS_AUC/1.2.826.0.1.3680043.8.498.11734583966325913475023864237373123772_METS_AUC_088.dcm"
        new_annotation.metadata = {
            ...new_annotation.metadata,
            viewportId: viewport.id,
            cam: viewport.getCamera(),
            toolName: tool_name,
            viewPlaneNormal: cam.viewPlaneNormal,
            viewUp: cam.viewUp,
            FrameOfReferenceUID: viewport.getFrameOfReferenceUID()
        }
        new_annotation.data.handles.points = points;
        cornerstone.tools.annotation.state.addAnnotation(new_annotation, viewport.element)
        cornerstone.tools.annotation.selection.setAnnotationSelected(new_annotation.annotationUID, true, false);

        this.viewer.viewports.map(x=>x.render())
        this.annotations[new_annotation.annotationUID] = { uid: new_annotation.annotationUID, label: new_annotation.data.label, ...new_annotation.metadata }
    }

    async deleteAnnotation(uid) {
        let annotation_info = this.annotations[uid];
        cornerstone.tools.annotation.state.removeAnnotation(annotation_info.uid)
        cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.viewer.renderingEngine,[annotation_info.viewportId]) 
        delete this.annotations[annotation_info.uid];
        await this.updateChart()
    }
    
    goToAnnotation(uid) {
        const annotation_info = this.annotations[uid];
        const viewport = [...this.viewer.viewports,this.viewer.auxViewport].find( x => x.id == annotation_info.viewportId);
        const annotation = cornerstone.tools.annotation.state.getAnnotation(uid);
        const centerPoint = Vector.avg(annotation.data.handles.points);
        if (viewport.type == "orthographic") {
            scrollViewportToPoint(viewport, centerPoint);
        } else { // stack
            const idx = viewport.imageIds.indexOf(annotation.metadata.referencedImageId)
            viewport.setImageIdIndex(idx);
        }
        cornerstone.tools.annotation.selection.setAnnotationSelected(uid, true, false);
        this.viewer.renderingEngine.renderViewports([annotation_info.viewportId]);
        cornerstone.tools.utilities.triggerAnnotationRenderForViewportIds(this.viewer.renderingEngine,[annotation_info.viewportId]) 
    }

    initChart() {    
        const div = document.getElementById("chart");

        var g = new Dygraph(div, [],
        {
            legend: 'always',
            // valueRange: [0.0, 1000],
            gridLineColor: 'white',
            // hideOverlayOnMouseOut: true,
            labels: ['seconds', 'Random'],
            highlightSeriesOpts: { strokeWidth: 3 },
            highlightSeriesBackgroundAlpha: 1,
            axes: {
                x: {
                    axisLabelFormatter: function(x) {
                        if (parseFloat(x))
                          return `${parseFloat(x)}s`;
                        return ''
                    }
                  }
            },
            underlayCallback: (function(canvas, area, g) {
                if (! this.viewer.study_uid || Object.keys(this.annotations).length == 0 ) {
                    return
                }
                var bottom_left = g.toDomCoords(this.viewer.selected_time, -20);  
                var left = bottom_left[0];
                canvas.fillStyle = "rgba(255, 255, 102, 1.0)";
                canvas.fillRect(left-2, area.y, 4, area.h);
            }).bind(this),
              pointClickCallback: function(event, p) {}
        });

        // div.addEventListener('mouseenter', () => {
        //     g.updateOptions({legend: 'follow'});
        // });

        // div.addEventListener('mouseleave', () => {
        //     g.updateOptions({legend: 'none'});
        // });

        const resizeObserver = new ResizeObserver(() => {
            g.resize(1,1); 
            // The above makes the chart small so offsetWidth etc reflects a nearly-empty parent div
            g.resize(viewer.chart.maindiv_.parentElement.offsetWidth-220,viewer.chart.maindiv_.parentElement.offsetHeight);
        });
        resizeObserver.observe(g.maindiv_.parentElement.parentElement);
    
        return g;
    }
}

export { AnnotationManager }
