import React from 'react';
import {Composition} from 'remotion';
import {calcularSketch, Sketch, SKETCH_DEMO} from './Sketch';

export const Root: React.FC = () => (
  <Composition
    id="Sketch"
    component={Sketch}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={SKETCH_DEMO.frames}
    defaultProps={SKETCH_DEMO}
    calculateMetadata={calcularSketch}
  />
);
