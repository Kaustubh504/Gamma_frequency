Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 7, S: 7 }
Dataflow {
SpatialMap(3,3) C;
TemporalMap(1,1) S;
TemporalMap(159,159) Y';
TemporalMap(4,4) R;
TemporalMap(6,6) K;
TemporalMap(28,28) X';
Cluster(1,P);
TemporalMap(1,1) R;
TemporalMap(1,1) C;
TemporalMap(1,1) S;
TemporalMap(1,1) Y';
TemporalMap(1,1) X';
SpatialMap(1,1) K;
}
}
}