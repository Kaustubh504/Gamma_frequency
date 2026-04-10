Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 7, S: 7 }
Dataflow {
TemporalMap(105,105) Y';
TemporalMap(19,19) K;
TemporalMap(1,1) S;
SpatialMap(3,3) C;
TemporalMap(4,4) R;
TemporalMap(4,4) X';
Cluster(19,P);
TemporalMap(1,1) S;
TemporalMap(2,2) R;
TemporalMap(13,13) K;
SpatialMap(1,1) C;
TemporalMap(2,2) X';
TemporalMap(1,1) Y';
}
}
}