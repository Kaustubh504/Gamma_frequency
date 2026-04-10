Network 0 {
Layer CONV {
Type: CONV
Dimensions { K: 64, C: 3, Y: 224, X: 224, R: 3, S: 3 }
Dataflow {
TemporalMap(2,2) C;
TemporalMap(181,181) X';
TemporalMap(2,2) R;
SpatialMap(41,41) K;
TemporalMap(3,3) S;
TemporalMap(148,148) Y';
Cluster(145,P);
TemporalMap(1,1) Y';
TemporalMap(1,1) S;
SpatialMap(1,1) X';
TemporalMap(1,1) R;
TemporalMap(1,1) K;
TemporalMap(1,1) C;
}
}
}