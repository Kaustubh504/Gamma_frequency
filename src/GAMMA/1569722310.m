Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
SpatialMap(3,3) C;
TemporalMap(2,2) S;
TemporalMap(134,134) X';
TemporalMap(110,110) Y';
TemporalMap(60,60) K;
TemporalMap(3,3) R;
Cluster(1,P);
SpatialMap(1,1) K;
TemporalMap(1,1) X';
TemporalMap(1,1) S;
TemporalMap(1,1) R;
TemporalMap(1,1) Y';
TemporalMap(1,1) C;
}
}
}