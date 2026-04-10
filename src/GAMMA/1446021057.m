Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(1,1) C;
TemporalMap(62,62) K;
SpatialMap(85,85) Y';
TemporalMap(3,3) S;
TemporalMap(171,171) X';
TemporalMap(2,2) R;
Cluster(31,P);
SpatialMap(1,1) Y';
TemporalMap(1,1) S;
TemporalMap(1,1) K;
TemporalMap(1,1) R;
TemporalMap(1,1) X';
TemporalMap(1,1) C;
}
}
}