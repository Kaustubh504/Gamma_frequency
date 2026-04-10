Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
SpatialMap(1,1) C;
TemporalMap(3,3) S;
TemporalMap(3,3) R;
TemporalMap(173,173) X';
TemporalMap(13,13) K;
TemporalMap(47,47) Y';
Cluster(10,P);
TemporalMap(1,1) S;
TemporalMap(1,1) C;
TemporalMap(1,1) X';
TemporalMap(1,1) Y';
SpatialMap(1,1) K;
TemporalMap(1,1) R;
}
}
}