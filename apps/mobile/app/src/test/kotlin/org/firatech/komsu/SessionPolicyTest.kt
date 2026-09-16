package org.firatech.komsu

import org.junit.Assert.*
import org.junit.Test

class SessionPolicyTest {
    @Test fun expiryBoundaryAndUnknownLifetime() {
        assertFalse(sessionExpired(1000,999))
        assertTrue(sessionExpired(1000,1000))
        assertTrue(sessionExpired(1000,1001))
        assertFalse(sessionExpired(0,Long.MAX_VALUE))
    }
}
