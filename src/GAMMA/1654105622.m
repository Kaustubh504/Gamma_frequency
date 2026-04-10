Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(2,2) C;
TemporalMap(65,65) X';
TemporalMap(102,102) Y';
TemporalMap(1,1) R;
SpatialMap(24,24) K;
TemporalMap(3,3) S;
Cluster(38,P);
TemporalMap(1,1) S;
TemporalMap(1,1) R;
TemporalMap(1,1) Y';
SpatialMap(1,1) X';
TemporalMap(1,1) C;
TemporalMap(1,1) K;
}
}
}