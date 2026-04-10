Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(215,215) X';
TemporalMap(18,18) K;
SpatialMap(68,68) Y';
TemporalMap(3,3) C;
TemporalMap(3,3) R;
TemporalMap(1,1) S;
Cluster(119,P);
TemporalMap(1,1) C;
TemporalMap(1,1) S;
TemporalMap(1,1) Y';
SpatialMap(1,1) X';
TemporalMap(1,1) K;
TemporalMap(1,1) R;
}
}
}