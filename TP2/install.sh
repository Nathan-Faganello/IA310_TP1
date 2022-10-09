sudo prosodyctl start
for i in {0..50};
do sudo prosodyctl register ship-$i localhost password-ship-$i;
done
for i in {0..50};
do sudo prosodyctl register planet-$i localhost password-planet-$i;
done