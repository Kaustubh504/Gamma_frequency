Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 7, S: 7 }
Dataflow {
TemporalMap(9,9) K;
TemporalMap(4,4) R;
TemporalMap(2,2) S;
TemporalMap(109,109) Y';
TemporalMap(2,2) C;
SpatialMap(52,52) X';
Cluster(133,P);
TemporalMap(9,9) K;
TemporalMap(33,33) X';
TemporalMap(1,1) C;
TemporalMap(1,1) S;
SpatialMap(1,1) Y';
TemporalMap(1,1) R;
}
}
}