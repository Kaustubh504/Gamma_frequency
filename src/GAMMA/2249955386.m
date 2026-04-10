Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(81,81) X';
TemporalMap(3,3) R;
TemporalMap(83,83) Y';
SpatialMap(29,29) K;
TemporalMap(1,1) C;
TemporalMap(3,3) S;
Cluster(61,P);
SpatialMap(1,1) Y';
TemporalMap(1,1) K;
TemporalMap(1,1) X';
TemporalMap(1,1) S;
TemporalMap(1,1) R;
TemporalMap(1,1) C;
}
}
}