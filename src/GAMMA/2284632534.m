Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(173,173) X';
TemporalMap(2,2) S;
SpatialMap(211,211) Y';
TemporalMap(3,3) R;
TemporalMap(16,16) K;
TemporalMap(1,1) C;
Cluster(14,P);
TemporalMap(1,1) R;
TemporalMap(1,1) C;
TemporalMap(1,1) S;
TemporalMap(1,1) Y';
SpatialMap(1,1) K;
TemporalMap(1,1) X';
}
}
}