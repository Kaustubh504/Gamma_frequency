Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
SpatialMap(52,52) K;
TemporalMap(1,1) C;
TemporalMap(2,2) R;
TemporalMap(203,203) Y';
TemporalMap(3,3) S;
TemporalMap(168,168) X';
Cluster(129,P);
SpatialMap(1,1) X';
TemporalMap(1,1) K;
TemporalMap(1,1) Y';
TemporalMap(1,1) R;
TemporalMap(1,1) S;
TemporalMap(1,1) C;
}
}
}