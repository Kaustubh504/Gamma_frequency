Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(3,3) S;
TemporalMap(64,64) X';
TemporalMap(36,36) K;
TemporalMap(2,2) R;
TemporalMap(153,153) Y';
SpatialMap(2,2) C;
Cluster(62,P);
SpatialMap(1,1) Y';
TemporalMap(1,1) C;
TemporalMap(1,1) X';
TemporalMap(1,1) K;
TemporalMap(1,1) S;
TemporalMap(1,1) R;
}
}
}